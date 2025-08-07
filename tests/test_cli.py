# ruff: noqa: E402
import os
import sys
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

# Ensure required environment variable for config import
os.environ.setdefault("SAMSARA_BEARER_TOKEN", "testing-token")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import types

mock_mapping = types.SimpleNamespace(
    load_position_tags=lambda: {},
    load_location_tags_and_timezones=lambda: {},
    load_never_positions=lambda: set(),
)
sys.modules.setdefault("src.mapping_loader", mock_mapping)

import src.add_drivers as add_module
import src.deactivate_drivers as deactivate_module

from src.add_drivers import app as add_main
from src.deactivate_drivers import app as deactivate_main

try:  # update command may not exist yet
    import src.update_drivers as update_module
    from src.update_drivers import app as update_main
except Exception:  # pragma: no cover - module optional
    update_module = None
    update_main = None

runner = CliRunner()


def _dummy_add_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Legal_Firstname": ["A"],
            "Legal_Lastname": ["B"],
            "Hire_Date": [pd.Timestamp("2020-01-01")],
            "Work_Location": ["HQ"],
            "State": ["CA"],
            "Employee_Status": ["Active"],
            "Position": ["Driver"],
        }
    )


class DummyPayload:
    username = "dummy"

    def model_dump(self, *, exclude_none: bool = True) -> dict:
        return {}


def _dummy_term_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Legal_Firstname": ["A"],
            "Legal_Lastname": ["B"],
            "Termination_Date": [pd.Timestamp("2020-02-01")],
            "Employee_Status": ["Terminated"],
            "Hire_Date": [pd.Timestamp("2020-01-01")],
        }
    )


def test_add_dry_run_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = tmp_path / "dummy.xlsx"
    dummy.touch()
    df = _dummy_add_df()
    monkeypatch.setattr(add_module, "read_xlsx", lambda path: df)
    monkeypatch.setattr(add_module, "get_driver_by_external_id", lambda *a, **k: None)
    monkeypatch.setattr(add_module, "add_driver", lambda *a, **k: True)
    monkeypatch.setattr(add_module, "row_to_payload", lambda row: DummyPayload())
    result = runner.invoke(add_main, ["--dry-run", str(dummy)])
    assert result.exit_code == 0


def test_add_dry_run_update_verbose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dummy = tmp_path / "dummy.xlsx"
    dummy.touch()
    df = _dummy_add_df()
    monkeypatch.setattr(add_module, "read_xlsx", lambda path: df)
    monkeypatch.setattr(
        add_module,
        "get_driver_by_external_id",
        lambda *a, **k: {"driverActivationStatus": "active"},
    )
    monkeypatch.setattr(add_module, "add_driver", lambda *a, **k: True)
    monkeypatch.setattr(
        add_module, "update_driver_by_external_id", lambda *a, **k: True
    )
    monkeypatch.setattr(add_module, "row_to_payload", lambda row: DummyPayload())
    result = runner.invoke(add_main, ["--dry-run", "--update", "-v", str(dummy)])
    assert result.exit_code == 0


def test_deactivate_dry_run_no_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dummy = tmp_path / "dummy.xlsx"
    dummy.touch()
    df = _dummy_term_df()
    monkeypatch.setattr(deactivate_module, "read_terminations_xlsx", lambda path: df)
    monkeypatch.setattr(
        deactivate_module,
        "get_driver_by_external_id",
        lambda *a, **k: {"driverActivationStatus": "active"},
    )
    result = runner.invoke(deactivate_main, ["--dry-run", "--no-fallback", str(dummy)])
    assert result.exit_code == 0


def test_deactivate_dry_run_fallback_verbose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dummy = tmp_path / "dummy.xlsx"
    dummy.touch()
    df = _dummy_term_df()
    monkeypatch.setattr(deactivate_module, "read_terminations_xlsx", lambda path: df)
    monkeypatch.setattr(
        deactivate_module, "get_driver_by_external_id", lambda *a, **k: None
    )
    monkeypatch.setattr(
        deactivate_module,
        "get_all_drivers",
        lambda include_deactivated=False: [
            {"id": "1", "name": "A B", "driverActivationStatus": "active"}
        ],
    )
    monkeypatch.setattr(
        deactivate_module,
        "find_driver_by_name",
        lambda drivers, first, last: drivers[0],
    )
    result = runner.invoke(deactivate_main, ["--dry-run", "-v", str(dummy)])
    assert result.exit_code == 0


@pytest.mark.skipif(update_main is None, reason="update drivers not implemented")
def test_update_dry_run_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = tmp_path / "dummy.xlsx"
    dummy.touch()
    df = _dummy_add_df()
    monkeypatch.setattr(update_module, "read_xlsx", lambda path: df)
    monkeypatch.setattr(
        update_module,
        "get_driver_by_external_id",
        lambda *a, **k: {"id": "1"},
    )
    monkeypatch.setattr(
        update_module, "update_driver_by_external_id", lambda *a, **k: True
    )
    monkeypatch.setattr(update_module, "row_to_payload", lambda row: DummyPayload())
    result = runner.invoke(update_main, ["--dry-run", str(dummy)])
    assert result.exit_code == 0
