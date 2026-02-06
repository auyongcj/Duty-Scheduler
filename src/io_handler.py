import pandas as pd
from typing import List, Set, Union
from .models import Employee, EmployeeType
from dateutil import parser
from datetime import date
import io

ExcelInput = Union[str, io.BytesIO]

def load_holidays(xls: ExcelInput) -> Set[date]:
    try:
        df = pd.read_excel(xls, sheet_name="Holidays")
        holiday_dates = pd.to_datetime(df["Date"]).dt.date.tolist()
        return set(holiday_dates)
    except Exception as e:
        print(f"Note: No 'Holidays' sheet found or error reading it: {e}")
        return set()

def load_employees(xls: ExcelInput) -> List[Employee]:
    df = pd.read_excel(xls, sheet_name="Employees")

    # Normalize headers to avoid Team/Team / TEAM issues
    df.columns = df.columns.astype(str).str.strip()

    employees = []
    for index, row in df.iterrows():
        name_raw = row.get("Name")
        if pd.isna(name_raw) or str(name_raw).strip() == "":
            print(f"Skipping row {index}: Name is missing.")
            continue
        name = str(name_raw).strip()

        team = str(row.get("Team", "")).strip()
        if not team:
            print(f"Warning: No team for {name}. Skipping row {index}.")
            continue

        role_str = str(row.get("Role", "Standard")).strip()
        try:
            role = EmployeeType(role_str)
        except ValueError:
            print(f"Warning: Invalid role '{role_str}' for {name}. Defaulting to Standard.")
            role = EmployeeType.STANDARD

        blackout_data = row.get("Blackouts(dates)") or row.get("Blackouts") or ""
        blackouts = parse_dates(blackout_data)

        ytd_raw = row.get("YTD", 0)
        ytd = int(ytd_raw) if not pd.isna(ytd_raw) else 0

        ph_bids_raw = row.get("PH Bids")
        ph_bids = parse_dates(ph_bids_raw)

        last_ph_raw = row.get("Last PH Date")
        last_ph_set = parse_dates(last_ph_raw)
        last_ph = max(last_ph_set) if last_ph_set else None

        employees.append(Employee(
            name=name,
            team=team,
            role=role,
            ytd_points=ytd,
            blackouts=blackouts,
            ph_bids=ph_bids,
            last_ph_date=last_ph
        ))

    return employees