import random
from datetime import date, timedelta
import pandas as pd
from typing import List, Dict, Set, Optional


FIRST_NAMES = [
    "Alex", "Alicia", "Ben", "Bianca", "Caleb", "Chloe", "Darren", "Diana", "Ethan", "Eva",
    "Felix", "Fiona", "Gavin", "Grace", "Hassan", "Hannah", "Ivan", "Ivy", "Jason", "Jasmine",
    "Kevin", "Kylie", "Liam", "Luna", "Marcus", "Mia", "Noah", "Nina", "Oscar", "Olivia",
    "Peter", "Priya", "Quinn", "Rachel", "Sam", "Sofia", "Tristan", "Tara", "Wes", "Zoe",
]
LAST_NAMES = [
    "Tan", "Lim", "Ng", "Lee", "Wong", "Goh", "Teo", "Ong", "Chua", "Koh",
    "Chan", "Low", "Yeo", "Toh", "Seah", "Lau", "Ho", "Nair", "Singh", "Kaur",
]

def _random_name(used: Set[str]) -> str:
    for _ in range(2000):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in used:
            used.add(name)
            return name
    base = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    i = 2
    while f"{base} {i}" in used:
        i += 1
    name = f"{base} {i}"
    used.add(name)
    return name

def _choose_role() -> str:
    # Updated to only use the two roles you requested
    roles = ["Standard", "Weekend-Only"]
    weights = [0.70, 0.30]  # Standard is usually the majority
    return random.choices(roles, weights=weights, k=1)[0]

def _random_dates_within(start: date, end: date, k: int) -> List[date]:
    if k <= 0: return []
    days = (end - start).days
    if days < 0: return []
    k = min(k, days + 1)
    return sorted({start + timedelta(days=random.randint(0, days)) for _ in range(k)})

def _fmt_dates(dates: List[date]) -> str:
    return ", ".join(d.strftime("%Y-%m-%d") for d in dates)

DEFAULT_TEAM_SIZES: Dict[str, int] = {
    # Type O teams
    "Black":  30,
    "White":  6,
    "Grey":   7,
    "Red":    9,
    # Type C teams
    "Blue":     8,
    "Yellow":   7,
    "Orange":   20,
    "Green":    9,
    "Purple":   8,
    "Violet":   7,
}

def generate_random_employee_db(
    output_path: str = "roster_database.xlsx",
    team_sizes: Optional[Dict[str, int]] = None,
    seed: Optional[int] = None,
    ytd_min: int = 0,
    ytd_max: int = 20,
    blackout_window_start: date = date(2026, 1, 1),
    blackout_window_end: date = date(2026, 12, 31),
    max_blackout_dates: int = 5,
    bid_probability: float = 0.35,
):
    if team_sizes is None:
        team_sizes = DEFAULT_TEAM_SIZES

    if seed is not None:
        random.seed(seed)

    holiday_data = {
        "Date": ["2026-01-01", "2026-02-17", "2026-04-03", "2026-05-01", "2026-08-09", "2026-12-25"],
        "Holiday Name": ["New Year's Day", "Lunar New Year", "Good Friday", "Labour Day", "National Day", "Christmas Day"],
    }
    df_holidays = pd.DataFrame(holiday_data)
    ph_dates = [pd.to_datetime(d).date() for d in holiday_data["Date"]]

    used_names: Set[str] = set()
    rows = []

    for team_name, count in team_sizes.items():
        for _ in range(count):
            name = _random_name(used_names)
            role = _choose_role()
            ytd = random.randint(ytd_min, ytd_max)

            num_blackouts = random.randint(0, max_blackout_dates)
            blackout_dates = _random_dates_within(blackout_window_start, blackout_window_end, num_blackouts)

            bids = []
            if random.random() < bid_probability:
                k = random.randint(1, min(3, len(ph_dates)))
                bids = random.sample(ph_dates, k)

            last_ph = ""
            if random.random() < 0.6:
                start_imm = date(2023, 1, 1)
                end_imm = date(2025, 12, 31)
                last_ph_dt = start_imm + timedelta(days=random.randint(0, (end_imm - start_imm).days))
                last_ph = last_ph_dt.strftime("%Y-%m-%d")

            rows.append({
                "Team": team_name,
                "Name": name,
                "Role": role,
                "YTD": ytd,
                "Blackouts": _fmt_dates(blackout_dates),
                "PH Bids": _fmt_dates(bids),
                "Last PH Date": last_ph,
            })

    df_employees = pd.DataFrame(rows)

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        df_employees.to_excel(writer, sheet_name="Employees", index=False)
        df_holidays.to_excel(writer, sheet_name="Holidays", index=False)

        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#D7E4BC", "border": 1})

        for sheet, cols in [("Employees", df_employees.columns), ("Holidays", df_holidays.columns)]:
            ws = writer.sheets[sheet]
            for col_num, value in enumerate(cols):
                ws.write(0, col_num, value, header_fmt)
            ws.freeze_panes(1, 0)

    print(f"Created: {output_path} (employees={sum(team_sizes.values())}, teams={team_sizes})")

if __name__ == "__main__":
    generate_random_employee_db(output_path="roster_database_random.xlsx")