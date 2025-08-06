import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import importlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class DummyUM:
    def make_unique(self, base: str) -> str:
        return base


def _setup_transformer(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SAMSARA_BEARER_TOKEN", "token")

    import mapping_loader as ml
    import username_manager as um
    import pandas as pd
    import pandas.api.types as pd_types

    if not hasattr(pd_types, "isna"):
        monkeypatch.setattr(pd_types, "isna", pd.isna, raising=False)

    monkeypatch.setattr(ml, "load_position_tags", lambda: {})
    monkeypatch.setattr(
        ml,
        "load_location_tags_and_timezones",
        lambda: {"LocA": {"tag_id": "tagloc", "timezone": "tz"}},
    )
    monkeypatch.setattr(ml, "load_never_positions", lambda: set())
    monkeypatch.setattr(um, "get_username_manager", lambda: DummyUM())

    import src.transformer as transformer

    importlib.reload(transformer)

    return transformer


def test_row_to_payload_missing_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    transformer = _setup_transformer(monkeypatch)
    row = SimpleNamespace(
        Position=None,
        Work_Location="LocA",
        Legal_Firstname="Jane",
        Legal_Lastname="Doe",
        Hire_Date=datetime(2024, 1, 1),
        State="CA",
    )
    payload = transformer.row_to_payload(row)
    assert payload.phone is None


def test_row_to_payload_with_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    transformer = _setup_transformer(monkeypatch)
    row = SimpleNamespace(
        Position=None,
        Work_Location="LocA",
        Legal_Firstname="John",
        Legal_Lastname="Smith",
        Hire_Date=datetime(2024, 1, 1),
        State="CA",
        Phone="555-1234",
    )
    payload = transformer.row_to_payload(row)
    assert payload.phone == "555-1234"
