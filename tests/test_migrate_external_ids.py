# ruff: noqa: E402
import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

# Ensure required environment variable for config import
os.environ.setdefault("SAMSARA_BEARER_TOKEN", "testing-token")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.migrate_external_ids as migrate_module
from src.migrate_external_ids import app as migrate_main
import src.samsara_client as sc
import logging

runner = CliRunner()


def _driver(name: str, hire_date: str) -> dict:
    """Helper to build a driver needing external ID."""
    return {"id": name, "name": name, "notes": f"Hire Date: {hire_date}"}


def test_backfill_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    drivers = [_driver("John Doe", "01-02-2020")]
    monkeypatch.setattr(sc, "get_all_drivers", lambda include_deactivated=True: drivers)
    calls: list[tuple] = []

    def fake_add(driver_id: str, key: str, value: str) -> bool:
        calls.append((driver_id, key, value))
        return True

    monkeypatch.setattr(sc, "add_external_id_to_driver", fake_add)

    logging.getLogger().handlers.clear()
    result = runner.invoke(migrate_main, ["backfill-external-ids", "--dry-run"])
    assert result.exit_code == 0
    assert "[DRY RUN] Would add paycomname" in result.stderr
    assert "Would update: 1 drivers" in result.stdout
    assert calls == []


def test_backfill_execute_with_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    drivers = [
        _driver("Jane Doe", "03-04-2021"),
        _driver("Bob Smith", "05-06-2022"),
    ]
    monkeypatch.setattr(sc, "get_all_drivers", lambda include_deactivated=True: drivers)
    calls: list[str] = []

    def fake_add(driver_id: str, key: str, value: str) -> bool:
        calls.append(driver_id)
        return driver_id != "Bob Smith"

    monkeypatch.setattr(sc, "add_external_id_to_driver", fake_add)

    logging.getLogger().handlers.clear()
    result = runner.invoke(migrate_main, ["backfill-external-ids", "--execute"])
    assert result.exit_code == 0
    # One driver succeeds, one fails
    assert "Added paycomname" in result.stderr
    assert "Failed to update Bob Smith" in result.stderr
    assert "Successfully updated: 1 drivers" in result.stdout
    assert "Failed: 1 drivers" in result.stdout
    assert calls == ["Jane Doe", "Bob Smith"]
