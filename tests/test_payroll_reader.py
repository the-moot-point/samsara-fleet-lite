# ruff: noqa: E402
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.payroll_reader import COLS, read_xlsx


def test_read_xlsx_filters_and_formats(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "Legal_Firstname": ["Anne", "Bob", "Cara"],
            "Legal_Lastname": ["A", "B", "C"],
            "Hire_Date": ["2020-01-01", "2021-02-02", "2022-03-03"],
            "Work_Location": ["Loc1", "Loc2", "Loc3"],
            "State": ["CA", "NY", "TX"],
            "Employee_Status": ["Active", "Inactive", "Active"],
            "Position": ["Driver", "Driver", "Manager"],
            "Extra": ["foo", "bar", "baz"],
        }
    )
    path = tmp_path / "employees.xlsx"
    df.to_excel(path, index=False)

    result = read_xlsx(str(path))

    assert list(result.columns) == COLS
    assert result.index.tolist() == [0, 1]
    assert (result.Employee_Status == "Active").all()
    assert pd.api.types.is_datetime64_any_dtype(result.Hire_Date)
    assert len(result) == 2
