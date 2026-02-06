# Duty-Schedule

The Duty Scheduler is an intelligent tool designed to automate the creation of fair and optimized duty rosters. It uses Google's OR-Tools (CP-SAT solver) to handle complex constraints and ensure equitable workload distribution among personnel based on a points system. The application is built with a user-friendly Streamlit web interface for easy configuration and visualization.

## Key Features

-   **Automated Roster Generation**: Creates complete duty schedules for a given period with the click of a button.
-   **Fairness-Driven Optimization**: Minimizes the difference in accumulated points across all employees, ensuring a balanced distribution of duties over time.
-   **Constraint-Based Logic**: Adheres to a comprehensive set of scheduling rules:
    -   **Coverage**: Ensures every required shift is filled.
    -   **Individual Limits**: Each person can only work one shift per day.
    -   **Rest Periods**: Enforces a mandatory rest day following a duty day.
    -   **Availability**: Respects individual employee blackout dates.
    -   **Team Categories**: Assigns duties based on team types (`Type C` vs. `Type O`) and organization-wide (`Org`) shifts.
    -   **Team Rotation**: Prevents the same team from being assigned consecutive shifts within the same duty category.
    -   **Role-Based Caps**: Limits the maximum number of shifts an employee can be assigned based on their role (e.g., "Standard", "Weekend-Only").
-   **Configurable Points System**: Allows customization of points awarded for different shift types (Weekday, Weekend, Public Holiday).
-   **Public Holiday (PH) Management**:
    -   **Immunity**: Employees who have recently worked a public holiday are granted immunity from subsequent PH duties for a configurable period (e.g., 2 years).
    -   **Bidding**: Prioritizes employees who bid for specific public holiday shifts.
-   **Interactive Web UI**: A Streamlit application provides an intuitive interface for uploading data, configuring parameters, and viewing results.
-   **Data Export**: Generates a multi-sheet Excel file containing the final roster, points analytics, and an updated master database with new point totals and PH history.

## How It Works

The application models the scheduling problem as a constraint satisfaction problem:

1.  **Input**: The user uploads an Excel file containing two sheets:
    *   `Employees`: A list of all personnel with their team, role, current year-to-date (YTD) points, blackout dates, and public holiday history/bids.
    *   `Holidays`: A list of official public holiday dates.
2.  **Configuration**: Through the web interface, the user defines the roster period, custom point values for each shift type, and the maximum number of shifts for each employee role.
3.  **Solving**: The `RosterSolver` uses Google's CP-SAT solver to find an optimal solution.
    *   It creates a boolean variable for every possible employee-shift assignment.
    *   It applies a series of constraints (e.g., "one shift per day," "enforce rest days," "respect blackouts").
    *   The primary objective is to **minimize the difference between the maximum and minimum total points** accrued by any employee, thus ensuring fairness.
4.  **Output**: If a valid solution is found, the application presents the results in a dashboard with tabs for the schedule, points analytics, and a downloadable, updated master database file.

## Getting Started

### Prerequisites

-   Python 3.8+

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/auyongcj/duty-scheduler.git
    cd duty-scheduler
    ```
1.  **Enable venv:**
    ```bash
    python -m venv .venv
    .\.venv\Scripts\Activate
    cd duty-scheduler
    ```
2.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Running the Application

1.  **Generate a sample database (optional):**
    A utility script is included to generate a test database file with randomized data.
    ```bash
    python generator.py
    ```
    This will create `roster_database_random.xlsx` in the root directory.

2.  **Start the Streamlit app:**
    ```bash
    streamlit run app.py
    ```

3.  Open your web browser and navigate to the local URL provided by Streamlit (usually `http://localhost:8501`).

### Input Data Format

The application requires an Excel file with two specific sheets:

#### `Employees` Sheet

| Column | Description | Example |
| :--- | :--- | :--- |
| **Team** | The employee's team name (e.g., "Blue", "Red"). | `Black` |
| **Name** | The employee's full name. | `Alex Tan` |
| **Role** | The employee's role. Used for applying shift caps. | `Standard` |
| **YTD** | The employee's current Year-To-Date points tally. | `15` |
| **Blackouts** | Comma-separated list of dates the employee is unavailable. | `2026-01-15, 2026-03-10` |
| **PH Bids**| Comma-separated list of public holidays the employee wants to work. | `2026-12-25` |
| **Last PH Date** | The date of the last public holiday the employee worked. | `2024-08-09` |

#### `Holidays` Sheet

| Column | Description | Example |
| :--- | :--- | :--- |
| **Date** | The date of the public holiday. | `2026-01-01` |
| **Holiday Name** | The name of the public holiday. | `New Year's Day` |

## Technology Stack

-   **Core Solver**: [Google OR-Tools (CP-SAT)](https://developers.google.com/optimization)
-   **Web Framework**: [Streamlit](https://streamlit.io/)
-   **Data Manipulation**: [Pandas](https://pandas.pydata.org/)
-   **Language**: Python
