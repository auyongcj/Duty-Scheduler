from ortools.sat.python import cp_model
from typing import List, Dict, Set
from datetime import date
from .models import Employee, Shift, EmployeeType, TYPE_C_TEAMS, TYPE_O_TEAMS
import pandas as pd
import random

DEFAULT_POINT_VALUES = {
    Shift.ORG_WEEKDAY_PM:      1.0,
    Shift.ORG_WEEKEND:         1.5,
    Shift.ORG_PH:              2.0,
    Shift.TYPE_C_WEEKDAY_PM:   1.0,
    Shift.TYPE_C_WEEKEND_AM:   1.5,
    Shift.TYPE_C_WEEKEND_PM:   1.5,
    Shift.TYPE_C_PH:           2.0,
    Shift.TYPE_O_WEEKDAY_PM:   1.0,
    Shift.TYPE_O_WEEKEND_AM:   1.5,
    Shift.TYPE_O_WEEKEND_PM:   1.5,
    Shift.TYPE_O_PH:           2.0,
}

class RosterSolver:
    def __init__(self, employees: List[Employee], date_range: List[date], public_holidays: Set[date],
                 point_values: Dict[Shift, float] = None, role_max_shifts: Dict[str, int] = None):
        self.employees       = employees
        self.date_range      = date_range
        self.public_holidays = public_holidays
        self.model           = cp_model.CpModel()
        self.variables       = {}
        self.errors          = []

        # Convert display point values (float) → internal integer weights (×10)
        pv = point_values if point_values else DEFAULT_POINT_VALUES
        self.point_weights = {s: round(v * 10) for s, v in pv.items()}

        # Per-role shift cap over the roster period
        self.role_max_shifts = role_max_shifts or {}

        # --- Team lookups ---
        self.teams          = sorted(set(emp.team for emp in employees))
        self.team_employees = {t: [e for e in employees if e.team == t] for t in self.teams}
        self.team_sizes     = {t: len(emps) for t, emps in self.team_employees.items()}
        self.emp_team       = {emp.name: emp.team for emp in employees}



    def _add_team_rotation_constraints(self):
            # Group shifts by category
            cat_shifts = {"ORG": [], "TYPE_C": [], "TYPE_O": []}
            for d in self.date_range:
                for s in self._get_shifts_for_day(d):
                    cat = "ORG" if "ORG" in s.name else ("TYPE_C" if "TYPE_C" in s.name else "TYPE_O")
                    cat_shifts[cat].append((d, s))

            for cat, slots in cat_shifts.items():
                for i in range(len(slots) - 1):
                    d1, s1 = slots[i]
                    d2, s2 = slots[i+1]
                    
                    # For every team, if a member works shift 1, 
                    # no member of that same team can work shift 2.
                    for t in self.teams:
                        team_members = [e.name for e in self.employees if e.team == t]
                        
                        vars_s1 = [self.variables[n, d1, s1] for n in team_members if (n, d1, s1) in self.variables]
                        vars_s2 = [self.variables[n, d2, s2] for n in team_members if (n, d2, s2) in self.variables]
                        
                        if vars_s1 and vars_s2:
                            # Constraint: Sum(Team at S1) + Sum(Team at S2) <= 1
                            self.model.Add(sum(vars_s1) + sum(vars_s2) <= 1)
    # ------------------------------------------------------------------
    # Shift layout per day type
    # ------------------------------------------------------------------
    def _get_shifts_for_day(self, d: date) -> List[Shift]:
        if d in self.public_holidays:
            return [Shift.ORG_PH, Shift.TYPE_C_PH, Shift.TYPE_O_PH]
        if d.weekday() >= 5:                         # Saturday / Sunday
            return [Shift.ORG_WEEKEND,
                    Shift.TYPE_C_WEEKEND_AM, Shift.TYPE_C_WEEKEND_PM,
                    Shift.TYPE_O_WEEKEND_AM, Shift.TYPE_O_WEEKEND_PM]
        return [Shift.ORG_WEEKDAY_PM, Shift.TYPE_C_WEEKDAY_PM, Shift.TYPE_O_WEEKDAY_PM]

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------
    def _candidates_for(self, d: date, s: Shift) -> List[Employee]:
        """Now returns all employees; eligibility is handled by variable existence."""
        return self.employees

    def _create_variables(self):
        all_teams = set(self.teams)
        type_c_pool = all_teams & TYPE_C_TEAMS
        type_o_pool = all_teams & TYPE_O_TEAMS

        for d in self.date_range:
            is_ph = d in self.public_holidays
            for s in self._get_shifts_for_day(d):
                # Determine which teams are allowed for this specific shift type
                if s.category in ["TYPE_C", "C"]:
                    allowed_teams = type_c_pool
                elif s.category in ["TYPE_O", "O"]:
                    allowed_teams = type_o_pool
                else:
                    allowed_teams = all_teams

                for emp in self.employees:
                    if emp.team in allowed_teams:
                        if emp.can_work(d, s, is_public_holiday=is_ph):
                            self.variables[(emp.name, d, s)] = self.model.NewBoolVar(f"{emp.name}_{d}_{s.name}")

    # ------------------------------------------------------------------
    # Coverage – every slot must be filled (exactly 1 person per shift per day)
    # ------------------------------------------------------------------
    def _add_coverage_constraints(self):
        for d in self.date_range:
            for s in self._get_shifts_for_day(d):
                # We only pick employees who have a valid variable for this (name, date, shift)
                relevant = [
                    self.variables[(emp.name, d, s)]
                    for emp in self.employees
                    if (emp.name, d, s) in self.variables
                ]
                
                if relevant:
                    self.model.Add(sum(relevant) == 1)
                else:
                    self.errors.append(
                        f"❌ Cannot fill: {d.strftime('%Y-%m-%d')} — {s.value}. No eligible employees found for this team category."
                    )

    # ------------------------------------------------------------------
    # At most one shift per employee per day
    # ------------------------------------------------------------------
    def _add_one_shift_per_day(self):
        for emp in self.employees:
            for d in self.date_range:
                day_vars = [
                    self.variables[(emp.name, d, s)]
                    for s in self._get_shifts_for_day(d)
                    if (emp.name, d, s) in self.variables
                ]
                if len(day_vars) > 1:
                    self.model.Add(sum(day_vars) <= 1)

    # ------------------------------------------------------------------
    # Mandatory 1-day rest
    # ------------------------------------------------------------------
    def _add_rest_constraints(self):
        for emp in self.employees:
            for i in range(len(self.date_range) - 1):
                today    = self.date_range[i]
                tomorrow = self.date_range[i + 1]

                today_vars = [
                    self.variables[(emp.name, today, s)]
                    for s in self._get_shifts_for_day(today)
                    if (emp.name, today, s) in self.variables
                ]
                tomorrow_vars = [
                    self.variables[(emp.name, tomorrow, s)]
                    for s in self._get_shifts_for_day(tomorrow)
                    if (emp.name, tomorrow, s) in self.variables
                ]
                if today_vars and tomorrow_vars:
                    self.model.Add(sum(today_vars) + sum(tomorrow_vars) <= 1)

    # ------------------------------------------------------------------
    # PH bidding – bidders get priority on Org PH slots
    # ------------------------------------------------------------------
    def _add_ph_bidding_constraints(self):
        for d in self.date_range:
            if d not in self.public_holidays:
                continue
            s = Shift.ORG_PH
            bidders = [emp for emp in self.employees if d in emp.ph_bids]
            bidder_vars = [
                self.variables[(emp.name, d, s)]
                for emp in bidders
                if (emp.name, d, s) in self.variables
            ]
            if bidder_vars:
                self.model.Add(sum(bidder_vars) == 1)

    # ------------------------------------------------------------------
    # Per-role maximum shift cap
    # ------------------------------------------------------------------
    def _add_role_max_shift_constraints(self):
        for emp in self.employees:
            max_s = self.role_max_shifts.get(emp.role.value)
            if max_s is None:
                continue
            emp_vars = [
                self.variables[(emp.name, d, s)]
                for d in self.date_range
                for s in self._get_shifts_for_day(d)
                if (emp.name, d, s) in self.variables
            ]
            if emp_vars:
                self.model.Add(sum(emp_vars) <= max_s)

    # ------------------------------------------------------------------
    # Objective: minimise point spread across all employees
    # ------------------------------------------------------------------
    def _set_fairness_objective(self):
        employee_totals = []
        for emp in self.employees:
            total = emp.ytd_points * 10
            for (name, d, s), var in self.variables.items():
                if name == emp.name:
                    total += var * self.point_weights.get(s, 10)
            employee_totals.append(total)

        max_pts = self.model.NewIntVar(0, 100000, "max_pts")
        min_pts = self.model.NewIntVar(0, 100000, "min_pts")
        for total in employee_totals:
            self.model.Add(max_pts >= total)
            self.model.Add(min_pts <= total)

        self.model.Minimize(max_pts - min_pts)

    # ------------------------------------------------------------------
    # Solve & extract results
    # ------------------------------------------------------------------
    def solve(self):
        self._create_variables()
        self._add_coverage_constraints()
        if self.errors:
            return None, None, self.errors
        self._add_team_rotation_constraints()
        self._add_one_shift_per_day()
        self._add_rest_constraints()
        self._add_ph_bidding_constraints()
        self._add_role_max_shift_constraints()
        self._set_fairness_objective()

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0
        status = solver.Solve(self.model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            roster_results = []
            for (emp_name, d, s), var in self.variables.items():
                if solver.Value(var) == 1:
                    roster_results.append({
                        "Date":     d,
                        "Day":      d.strftime('%A'),
                        "Employee": emp_name,
                        "Team":     self.emp_team[emp_name],
                        "Category": s.category,
                        "Shift":    s.value,
                    })

            summary_results = []
            for emp in self.employees:
                new_points = 0
                for (name, d, s), var in self.variables.items():
                    if name == emp.name and solver.Value(var) == 1:
                        new_points += self.point_weights.get(s, 10)

                summary_results.append({
                    "Employee":        emp.name,
                    "Team":            emp.team,
                    "Starting Points": emp.ytd_points,
                    "Points Earned":   new_points / 10,
                    "Total Points":    emp.ytd_points + (new_points / 10),
                })

            return pd.DataFrame(roster_results), pd.DataFrame(summary_results), []

        return None, None, ["⚠️ Logic Conflict: Constraints are too tight to find a fair balance."]
