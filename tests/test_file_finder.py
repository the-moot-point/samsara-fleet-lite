import sys
from pathlib import Path
from typing import Tuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.file_finder import PayrollFileFinder


def test_find_latest_reports(
    payroll_finder: PayrollFileFinder, sample_report_dirs: Tuple[Path, Path]
) -> None:
    hires_dir, terms_dir = sample_report_dirs
    assert payroll_finder.find_latest_hire_report() == (
        hires_dir / "20240201000000_New Hires Report_eeff0011_.xlsx"
    )
    assert payroll_finder.find_latest_term_report() == (
        terms_dir / "20240301000000_New Terms Report_66778899_.xlsx"
    )
    result = PayrollFileFinder._find_latest_file(
        hires_dir, PayrollFileFinder.NEW_HIRE_PATTERN, "New Hires"
    )
    assert result == hires_dir / "20240201000000_New Hires Report_eeff0011_.xlsx"


def test_missing_directories(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    finder = PayrollFileFinder(hires_dir=missing, terms_dir=missing)
    assert finder.find_latest_hire_report() is None
    assert finder.find_latest_term_report() is None
    assert (
        PayrollFileFinder._find_latest_file(
            missing, PayrollFileFinder.NEW_HIRE_PATTERN, "New Hires"
        )
        is None
    )


def test_get_file_info(
    payroll_finder: PayrollFileFinder, sample_report_dirs: Tuple[Path, Path]
) -> None:
    hires_dir, _ = sample_report_dirs
    file_path = hires_dir / "20240201000000_New Hires Report_eeff0011_.xlsx"
    info = payroll_finder.get_file_info(file_path)
    assert info["name"] == file_path.name
    assert info["path"] == str(file_path)
    assert info["exists"] is True
    assert info["size"] == file_path.stat().st_size
    assert info["timestamp"] == "2024-02-01T00:00:00"
    assert isinstance(info["age_hours"], float) and info["age_hours"] >= 0


def test_list_all_reports(payroll_finder: PayrollFileFinder) -> None:
    reports = payroll_finder.list_all_reports()
    assert [r["name"] for r in reports["hire_reports"]] == [
        "20240201000000_New Hires Report_eeff0011_.xlsx",
        "20240101000000_New Hires Report_aabbccdd_.xlsx",
    ]
    assert [r["name"] for r in reports["term_reports"]] == [
        "20240301000000_New Terms Report_66778899_.xlsx",
        "20240101000000_New Terms Report_22334455_.xlsx",
    ]
    for key in ("hire_reports", "term_reports"):
        for item in reports[key]:
            assert {"path", "name", "size", "exists"}.issubset(item)
            assert "timestamp" in item

