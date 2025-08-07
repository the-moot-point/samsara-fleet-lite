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

import src.main as main_module
import src.username_manager as username_manager_module
import src.samsara_client as samsara_client_module

runner = CliRunner()


def test_process_calls_modules_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_deactivate(*args, **kwargs) -> None:
        calls.append("deactivate")

    def fake_add(*args, **kwargs) -> None:
        calls.append("add")

    monkeypatch.setattr(main_module.deactivate_drivers, "deactivate", fake_deactivate)
    monkeypatch.setattr(main_module.add_drivers, "add", fake_add)

    result = runner.invoke(main_module.app, ["process"])
    assert result.exit_code == 0
    assert calls == ["deactivate", "add"]
    assert "Step 1: Processing Terminations" in result.output
    assert "Step 2: Processing New Hires" in result.output
    assert result.output.index("Step 1: Processing Terminations") < result.output.index(
        "Step 2: Processing New Hires"
    )


def test_process_handles_missing_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def missing_deactivate(*args, **kwargs) -> None:
        calls.append("deactivate")
        raise FileNotFoundError

    def missing_add(*args, **kwargs) -> None:
        calls.append("add")
        raise FileNotFoundError

    monkeypatch.setattr(main_module.deactivate_drivers, "deactivate", missing_deactivate)
    monkeypatch.setattr(main_module.add_drivers, "add", missing_add)

    result = runner.invoke(main_module.app, ["process"])
    assert result.exit_code == 0
    assert calls == ["deactivate", "add"]
    assert "No termination reports found" in result.output
    assert "No hire reports found" in result.output


def test_status_reports_and_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hires_dir = tmp_path / "hires"
    terms_dir = tmp_path / "terms"
    hires_dir.mkdir()
    terms_dir.mkdir()

    class DummyFinder:
        def __init__(self) -> None:
            self.hires_dir = hires_dir
            self.terms_dir = terms_dir
            self.calls = 0

        def list_all_reports(self, which: str) -> dict:  # noqa: D401
            """Return no reports and count calls."""
            self.calls += 1
            return {}

    finder = DummyFinder()
    monkeypatch.setattr(main_module, "PayrollFileFinder", lambda: finder)

    class DummyManager:
        def get_all_usernames(self) -> list[str]:
            return ["a", "b"]

    monkeypatch.setattr(
        username_manager_module, "get_username_manager", lambda: DummyManager()
    )
    monkeypatch.setattr(
        samsara_client_module, "get_drivers_by_status", lambda status: []
    )

    result = runner.invoke(main_module.app, ["status"])
    assert result.exit_code == 0
    assert "Configured Directories" in result.output
    assert "New Hires: No reports found" in result.output
    assert "Terms:     No reports found" in result.output
    assert finder.calls == 1
