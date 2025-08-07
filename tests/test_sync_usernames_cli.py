# ruff: noqa: E402
import os
import sys
from pathlib import Path
from typing import Set

import pytest
from typer.testing import CliRunner

os.environ.setdefault("SAMSARA_BEARER_TOKEN", "testing-token")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.sync_usernames as sync_module  # noqa: E402
from src.sync_usernames import app as username_app  # noqa: E402


runner = CliRunner()


class DummyManager:
    def __init__(self, usernames: Set[str]):
        self.usernames = set(u.lower() for u in usernames)

    def get_all_usernames(self) -> Set[str]:
        return set(self.usernames)

    def sync_with_samsara(self, samsara_usernames: Set[str]) -> None:
        self.usernames.update(u.lower() for u in samsara_usernames)

    def exists(self, username: str) -> bool:
        return username.lower() in self.usernames

    def check_available(self, base_username: str) -> str:
        base = base_username.lower()
        if base not in self.usernames:
            return base
        counter = 2
        while True:
            candidate = f"{base}{counter}"
            if candidate not in self.usernames:
                return candidate
            counter += 1


def test_status_mismatched(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = DummyManager({"alice", "bob"})
    monkeypatch.setattr(
        sync_module, "get_username_manager", lambda path=None: manager
    )
    monkeypatch.setattr(
        sync_module,
        "get_driver_usernames",
        lambda include_deactivated=True: {"alice": "active", "charlie": "deactivated"},
    )
    result = runner.invoke(username_app, ["status"])
    assert result.exit_code == 0
    assert "In CSV but not in Samsara: 1" in result.output
    assert "In Samsara but not in CSV: 1" in result.output


def test_status_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = DummyManager(set())
    monkeypatch.setattr(
        sync_module, "get_username_manager", lambda path=None: manager
    )
    def _boom(*_args, **_kwargs):  # noqa: ANN001
        raise RuntimeError("boom")
    monkeypatch.setattr(sync_module, "get_driver_usernames", _boom)
    result = runner.invoke(username_app, ["status"])
    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)


def test_sync_success(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = DummyManager({"alice"})
    monkeypatch.setattr(
        sync_module, "get_username_manager", lambda path=None: manager
    )
    monkeypatch.setattr(
        sync_module,
        "get_all_drivers",
        lambda include_deactivated=True: [
            {"username": "alice", "driverActivationStatus": "active"},
            {"username": "bob", "driverActivationStatus": "active"},
        ],
    )
    result = runner.invoke(username_app, ["sync"])
    assert result.exit_code == 0
    assert "Successfully synced! Added 1 new usernames." in result.output
    assert "Total usernames in database: 2" in result.output


def test_sync_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = DummyManager(set())
    monkeypatch.setattr(
        sync_module, "get_username_manager", lambda path=None: manager
    )
    def _fail(*_args, **_kwargs):  # noqa: ANN001
        raise RuntimeError("api down")
    monkeypatch.setattr(sync_module, "get_all_drivers", _fail)
    result = runner.invoke(username_app, ["sync"])
    assert result.exit_code != 0
    assert "Sync failed: api down" in result.output


def test_check_existing_username(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = DummyManager({"jdoe"})
    monkeypatch.setattr(
        sync_module, "get_username_manager", lambda path=None: manager
    )
    result = runner.invoke(username_app, ["check", "John", "Doe"])
    assert result.exit_code == 0
    assert "Base username 'jdoe' already exists." in result.output
    assert "Would generate: jdoe2" in result.output


def test_stats_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = DummyManager({"alice", "bob1", "bob2"})
    monkeypatch.setattr(
        sync_module, "get_username_manager", lambda path=None: manager
    )
    result = runner.invoke(username_app, ["stats"])
    assert result.exit_code == 0
    assert "Total usernames: 3" in result.output
    assert "Modified usernames (with numbers): 2" in result.output
    assert "bob: 2 variations" in result.output
