
from enum import Enum
from dataclasses import dataclass, field
from typing import Set, Optional
from datetime import date

# ---------------------------------------------------------------------------
# Team → duty-category mapping  (notes.txt)
# ---------------------------------------------------------------------------
TYPE_C_TEAMS = {"Blue", "Yellow", "Orange", "Green", "Purple", "Violet"}
TYPE_O_TEAMS = {"Black", "White", "Grey", "Red"}

class EmployeeType(Enum):
    STANDARD = "Standard"
    WEEKEND_ONLY = "Weekend-Only"

class Shift(Enum):
    # Org-level shifts (open to all teams)
    ORG_WEEKDAY_PM    = "Org Weekday PM"
    ORG_WEEKEND       = "Org Weekend"
    ORG_PH            = "Org PH"
    # Type C shifts (Blue, Yellow, Orange, Green, Purple, Violet)
    TYPE_C_WEEKDAY_PM = "Type C Weekday PM"
    TYPE_C_WEEKEND_AM = "Type C Weekend AM"
    TYPE_C_WEEKEND_PM = "Type C Weekend PM"
    TYPE_C_PH         = "Type C PH"
    # Type O shifts (Black, White, Grey, Red)
    TYPE_O_WEEKDAY_PM = "Type O Weekday PM"
    TYPE_O_WEEKEND_AM = "Type O Weekend AM"
    TYPE_O_WEEKEND_PM = "Type O Weekend PM"
    TYPE_O_PH         = "Type O PH"

    @property
    def is_org(self) -> bool:
        return self in (Shift.ORG_WEEKDAY_PM, Shift.ORG_WEEKEND, Shift.ORG_PH)

    @property
    def is_type_c(self) -> bool:
        return self in (Shift.TYPE_C_WEEKDAY_PM, Shift.TYPE_C_WEEKEND_AM,
                        Shift.TYPE_C_WEEKEND_PM, Shift.TYPE_C_PH)

    @property
    def is_type_o(self) -> bool:
        return self in (Shift.TYPE_O_WEEKDAY_PM, Shift.TYPE_O_WEEKEND_AM,
                        Shift.TYPE_O_WEEKEND_PM, Shift.TYPE_O_PH)

    @property
    def category(self) -> str:
        if self.is_org:    return "Org"
        if self.is_type_c: return "Type C"
        return "Type O"

@dataclass
class Employee:
    name: str
    team: str
    role: EmployeeType
    ytd_points: int = 0
    blackouts: Set[date] = field(default_factory=set)
    ph_bids: Set[date] = field(default_factory=set)
    last_ph_date: Optional[date] = None

    def is_immune(self, day: date, years_threshold: int = 2) -> bool:
        if not self.last_ph_date:
            return False
        try:
            immunity_end_date = self.last_ph_date.replace(year=self.last_ph_date.year + years_threshold)
        except ValueError:
            immunity_end_date = self.last_ph_date.replace(year=self.last_ph_date.year + years_threshold, day=28)
        return day < immunity_end_date

    def can_work(self, day: date, shift: Shift, is_public_holiday: bool = False) -> bool:
        if day in self.blackouts:
            return False
        if is_public_holiday and self.is_immune(day):
            return False

        if is_public_holiday:
            return shift in (Shift.ORG_PH, Shift.TYPE_C_PH, Shift.TYPE_O_PH)

        if day.weekday() >= 5:  # weekend
            return shift in (Shift.ORG_WEEKEND,
                             Shift.TYPE_C_WEEKEND_AM, Shift.TYPE_C_WEEKEND_PM,
                             Shift.TYPE_O_WEEKEND_AM, Shift.TYPE_O_WEEKEND_PM)

        return shift in (Shift.ORG_WEEKDAY_PM, Shift.TYPE_C_WEEKDAY_PM, Shift.TYPE_O_WEEKDAY_PM)
