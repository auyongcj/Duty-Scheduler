import os
import streamlit as st
import pandas as pd
from src.io_handler import load_employees, load_holidays
from datetime import timedelta, date
from src.solver import RosterSolver
from src.models import Shift
from typing import List
import io
import hashlib

# --- PAGE CONFIG ---
st.set_page_config(page_title="Duty Roster Planner", layout="wide", page_icon="🗓️")

# --- CUSTOM CSS FOR STYLING ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #ff4b4b; color: white; }
    .stDownloadButton>button { width: 100%; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'roster_df' not in st.session_state:
    st.session_state.roster_df = None
if 'summary_df' not in st.session_state:
    st.session_state.summary_df = None
if 'employees' not in st.session_state:
    st.session_state.employees = None
if 'holidays' not in st.session_state:
    st.session_state.holidays = None
if "uploaded_bytes" not in st.session_state:
    st.session_state.uploaded_bytes = None
if "uploaded_hash" not in st.session_state:
    st.session_state.uploaded_hash = None
if "uploaded_name" not in st.session_state:
    st.session_state.uploaded_name = None
if "final_database" not in st.session_state:
    st.session_state.final_database = None
if "loaded_hash" not in st.session_state:
    st.session_state.loaded_hash = None

# --- PATH CONSTANTS ---
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER    = os.path.join(BASE_DIR, "data")
TEMP_FILE_PATH = os.path.join(DATA_FOLDER, "temp_data.xlsx")

# --- UTILS ---
# Within a single day AM slots sort before PM slots; everything else is 0
_SHIFT_SLOT_ORDER = {
    "Type C Weekend AM": 0, "Type C Weekend PM": 1,
    "Type O Weekend AM": 0, "Type O Weekend PM": 1,
}

def _sort_roster(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by Date then by AM-before-PM within each day."""
    return df.assign(_ord=df["Shift"].map(_SHIFT_SLOT_ORDER).fillna(0)) \
             .sort_values(["Date", "_ord"]) \
             .drop(columns=["_ord"])

def get_date_list(start_date: date, end_date: date) -> List[date]:
    if start_date > end_date: return []
    delta = end_date - start_date
    return [start_date + timedelta(days=i) for i in range(delta.days + 1)]

# --- SIDEBAR: INPUTS & CONFIG ---
with st.sidebar:
    st.title("⚙️ Roster Config")
    st.info("Upload your database and select dates to begin.")

    uploaded_file = st.file_uploader("Upload Employee Excel", type=["xlsx"], key="uploader_db")

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_hash  = hashlib.sha256(file_bytes).hexdigest()

        # ALWAYS persist bytes + metadata
        st.session_state.uploaded_bytes = file_bytes
        st.session_state.uploaded_hash  = file_hash
        st.session_state.uploaded_name  = uploaded_file.name

        # Load employees/holidays if not loaded yet OR if new file
        if (st.session_state.employees is None) or (st.session_state.get("loaded_hash") != file_hash):
            st.session_state.employees = load_employees(io.BytesIO(file_bytes))
            st.session_state.holidays  = load_holidays(io.BytesIO(file_bytes))
            st.session_state.loaded_hash = file_hash

            # Reset results for a new dataset
            st.session_state.roster_df = None
            st.session_state.summary_df = None
            st.session_state.final_database = None

            st.rerun()
        

    st.divider()

    st.subheader("Date Range")
    date_range = st.date_input(
        "Roster Period:",
        value=[date.today(), date.today() + timedelta(days=13)],
    )

    st.divider()

    st.subheader("Point Values")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Org Shifts")
        pt_org_wd  = st.number_input("Org Weekday PM",  min_value=0.0, value=1.0, step=0.5)
        pt_org_we  = st.number_input("Org Weekend",     min_value=0.0, value=1.5, step=0.5)
        pt_org_ph  = st.number_input("Org PH",          min_value=0.0, value=2.0, step=0.5)
    with c2:
        st.caption("Type C Shifts")
        pt_c_wd    = st.number_input("Type C Weekday PM", min_value=0.0, value=1.0, step=0.5)
        pt_c_am    = st.number_input("Type C Weekend AM", min_value=0.0, value=1.5, step=0.5)
        pt_c_pm    = st.number_input("Type C Weekend PM", min_value=0.0, value=1.5, step=0.5)
        pt_c_ph    = st.number_input("Type C PH",         min_value=0.0, value=2.0, step=0.5)
    with c3:
        st.caption("Type O Shifts")
        pt_o_wd    = st.number_input("Type O Weekday PM", min_value=0.0, value=1.0, step=0.5)
        pt_o_am    = st.number_input("Type O Weekend AM", min_value=0.0, value=1.5, step=0.5)
        pt_o_pm    = st.number_input("Type O Weekend PM", min_value=0.0, value=1.5, step=0.5)
        pt_o_ph    = st.number_input("Type O PH",         min_value=0.0, value=2.0, step=0.5)

    custom_points = {
        Shift.ORG_WEEKDAY_PM:      pt_org_wd,
        Shift.ORG_WEEKEND:         pt_org_we,
        Shift.ORG_PH:              pt_org_ph,
        Shift.TYPE_C_WEEKDAY_PM:   pt_c_wd,
        Shift.TYPE_C_WEEKEND_AM:   pt_c_am,
        Shift.TYPE_C_WEEKEND_PM:   pt_c_pm,
        Shift.TYPE_C_PH:           pt_c_ph,
        Shift.TYPE_O_WEEKDAY_PM:   pt_o_wd,
        Shift.TYPE_O_WEEKEND_AM:   pt_o_am,
        Shift.TYPE_O_WEEKEND_PM:   pt_o_pm,
        Shift.TYPE_O_PH:           pt_o_ph,
    }

    st.divider()

    st.subheader("Role Limits")
    # Dynamic default: ceil(n_days / 5), minimum 3.  Resets when the date range changes.
    n_days      = (date_range[1] - date_range[0]).days + 1 if len(date_range) == 2 else 14
    default_cap = 3 

    role_max_shifts = {}
    if st.session_state.employees:
        roles = sorted(set(e.role.value for e in st.session_state.employees))
        cols = st.columns(len(roles))
        for col, role in zip(cols, roles):
            with col:
                st.caption(role)
                role_max_shifts[role] = st.number_input(
                    "Max Shifts",
                    min_value=0, 
                    value=default_cap, 
                    step=1,
                    # Keeping n_days in the key ensures it resets if the user picks a new date range
                    key=f"max_shifts_{role}_{n_days}", 
                )
    else:
        st.caption("Upload a file to configure role limits.")

    if st.button("🚀 Generate Roster"):
        if not st.session_state.employees:
            st.error("Please upload an Excel file first!")
        elif len(date_range) != 2:
            st.error("Please select a valid start and end date.")
        else:
            start_dt, end_dt = date_range
            dates = get_date_list(start_dt, end_dt)
            solver = RosterSolver(st.session_state.employees, dates, st.session_state.holidays,
                                  point_values=custom_points, role_max_shifts=role_max_shifts)

            with st.spinner("AI is optimising shifts..."):
                roster_df, summary_df, error_list = solver.solve()
                if roster_df is not None:
                    st.session_state.roster_df = roster_df
                    st.session_state.summary_df = summary_df
                    
                    # --- AUTO-GENERATE UPDATED DATABASE ---
                    try:
                        all_sheets = pd.read_excel(io.BytesIO(st.session_state.uploaded_bytes), sheet_name=None)
                        df_emp = all_sheets["Employees"]
                        
                        # Update Points
                        point_map = dict(zip(summary_df["Employee"], summary_df["Total Points"]))
                        df_emp["YTD"] = df_emp["Name"].map(point_map).fillna(df_emp["YTD"])
                        
                        # Update PH Dates
                        ph_worked = roster_df[roster_df["Shift"].str.contains("PH", na=False)]
                        for _, row in ph_worked.iterrows():
                            df_emp.loc[df_emp["Name"] == row["Employee"], "Last PH Date"] = row["Date"]
                        
                        update_buffer = io.BytesIO()
                        with pd.ExcelWriter(update_buffer, engine="xlsxwriter") as writer:
                            for sheet_name, df in all_sheets.items():
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        st.session_state.final_database = update_buffer.getvalue()
                        st.sidebar.success("Roster & Database Ready!")
                    except Exception as e:
                        st.sidebar.error(f"Error prepping database: {e}")
                else:
                    st.error("Roster Failed. Check availability.")
                    for err in error_list: st.write(err)

# --- MAIN CONTENT AREA ---
st.title("🗓️ Duty Roster Planner")

if st.session_state.roster_df is None:
    # --- WELCOME / PRE-SOLVE VIEW ---
    st.write("### Welcome! 👋")
    st.write("Use the sidebar on the left to upload your database and generate a new schedule.")

    if st.session_state.employees:
        st.divider()
        st.subheader("Personnel Status Overview")
        display_data = []
        for e in st.session_state.employees:
            display_data.append({
                "Name": e.name, "Team": e.team, "Role": e.role.value, "YTD Points": e.ytd_points,
                "PH Status": "🛡️ Immune" if e.is_immune(date.today()) else "✅ Available",
                "Last PH": e.last_ph_date.strftime('%Y-%m-%d') if e.last_ph_date else "Never"
            })
        st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)

else:
    # --- POST-SOLVE DASHBOARD ---
    tab1, tab2, tab3 = st.tabs(["📅 Schedule", "📊 Points Analytics", "💾 Finalise & Export"])

    with tab1:
        st.subheader("Optimised Schedule")
        roster_df = st.session_state.roster_df

        # Sub-tabs by duty category
        sub_tabs = st.tabs(["🏢 Org", "🔵 Type C", "🟠 Type O"])

        with sub_tabs[0]:
            st.dataframe(
                _sort_roster(roster_df[roster_df["Category"] == "Org"]),
                use_container_width=True, hide_index=True)

        with sub_tabs[1]:
            st.dataframe(
                _sort_roster(roster_df[roster_df["Category"] == "Type C"]),
                use_container_width=True, hide_index=True)

        with sub_tabs[2]:
            st.dataframe(
                _sort_roster(roster_df[roster_df["Category"] == "Type O"]),
                use_container_width=True, hide_index=True)

        # Download multi-sheet roster
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            # 1. Org Roster
            _sort_roster(roster_df[roster_df["Category"] == "Org"]).to_excel(
                writer, index=False, sheet_name="Org Roster")
            # 2. Type C Roster
            _sort_roster(roster_df[roster_df["Category"] == "Type C"]).to_excel(
                writer, index=False, sheet_name="Type C Roster")
            # 3. Type O Roster
            _sort_roster(roster_df[roster_df["Category"] == "Type O"]).to_excel(
                writer, index=False, sheet_name="Type O Roster")
            # 4. Stats
            st.session_state.summary_df.to_excel(writer, index=False, sheet_name="Stats")
            # 5. Reupload-ready sheets (updated Employees + original Holidays)
            all_sheets = pd.read_excel(io.BytesIO(st.session_state.uploaded_bytes), sheet_name=None)
            df_emp = all_sheets["Employees"]
            point_map = dict(zip(st.session_state.summary_df["Employee"],
                                 st.session_state.summary_df["Total Points"]))
            df_emp["YTD"] = df_emp["Name"].map(point_map).fillna(df_emp["YTD"])
            ph_worked = roster_df[roster_df["Shift"].str.contains("PH", na=False)]
            for _, row in ph_worked.iterrows():
                df_emp.loc[df_emp["Name"] == row["Employee"], "Last PH Date"] = row["Date"]
            df_emp.to_excel(writer, index=False, sheet_name="Employees")
            if "Holidays" in all_sheets:
                all_sheets["Holidays"].to_excel(writer, index=False, sheet_name="Holidays")

        st.download_button("📥 Download Roster (.xlsx)", buffer.getvalue(), f"Roster_{date.today()}.xlsx", "application/vnd.ms-excel")

    with tab2:
        st.subheader("Points Analytics")
        roster_df  = st.session_state.roster_df
        summary_df = st.session_state.summary_df
        teams = sorted(summary_df["Team"].unique())

        # Shift counts by category
        org_counts    = roster_df[roster_df["Category"] == "Org"].groupby("Employee").size()
        type_c_counts = roster_df[roster_df["Category"] == "Type C"].groupby("Employee").size()
        type_o_counts = roster_df[roster_df["Category"] == "Type O"].groupby("Employee").size()

        # Overall fairness delta
        overall_delta = summary_df["Total Points"].max() - summary_df["Total Points"].min()

        sub_tabs = st.tabs([f"👥 {t}" for t in teams])

        for i, team in enumerate(teams):
            with sub_tabs[i]:
                df = summary_df[summary_df["Team"] == team].copy()
                df["Org Shifts"]    = df["Employee"].map(org_counts).fillna(0).astype(int)
                df["Type C Shifts"] = df["Employee"].map(type_c_counts).fillna(0).astype(int)
                df["Type O Shifts"] = df["Employee"].map(type_o_counts).fillna(0).astype(int)

                team_delta = df["Total Points"].max() - df["Total Points"].min()

                c1, c2 = st.columns(2)
                c1.metric("Overall Fairness Delta", f"{overall_delta:.1f} pts")
                c2.metric("Team Fairness Delta",    f"{team_delta:.1f} pts")

                st.dataframe(
                    df[["Employee", "Starting Points", "Org Shifts", "Type C Shifts", "Type O Shifts", "Points Earned", "Total Points"]],
                    use_container_width=True, hide_index=True
                )

    with tab3:
        st.subheader("💾 Save & Update Database")
        if st.session_state.final_database is not None:
            st.success("The updated master database (including new points and PH history) is ready.")
            st.download_button(
                label="📥 Download Updated Master Database",
                data=st.session_state.final_database,
                file_name=f"Master_Database_Updated_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Generate a roster first to enable database updates.")