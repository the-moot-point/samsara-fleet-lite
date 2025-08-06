import pandas as pd

COLS = [
    "Legal_Firstname",
    "Legal_Lastname",
    "Hire_Date",
    "Work_Location",
    "State",
    "Employee_Status",
    "Position",
]


def read_xlsx(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, dtype=str)
    df = df[COLS]  # keep only needed columns
    df = df[df.Employee_Status == "Active"]
    df.Hire_Date = pd.to_datetime(df.Hire_Date)
    return df.reset_index(drop=True)
