import sys
from pathlib import Path
from typing import Tuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.file_finder import PayrollFileFinder


@pytest.fixture
def sample_report_dirs(tmp_path: Path) -> Tuple[Path, Path]:
    """Create temporary hire and term report directories with sample files."""
    hires_dir = tmp_path / "hires"
    terms_dir = tmp_path / "terms"
    hires_dir.mkdir()
    terms_dir.mkdir()

    hire_files = [
        "20240101000000_New Hires Report_aabbccdd_.xlsx",
        "20240201000000_New Hires Report_eeff0011_.xlsx",
    ]
    term_files = [
        "20240101000000_New Terms Report_22334455_.xlsx",
        "20240301000000_New Terms Report_66778899_.xlsx",
    ]

    for name in hire_files:
        (hires_dir / name).touch()
    for name in term_files:
        (terms_dir / name).touch()

    return hires_dir, terms_dir


@pytest.fixture
def payroll_finder(sample_report_dirs: Tuple[Path, Path]) -> PayrollFileFinder:
    """Return a PayrollFileFinder configured with the sample directories."""
    hires_dir, terms_dir = sample_report_dirs
    return PayrollFileFinder(hires_dir=hires_dir, terms_dir=terms_dir)

