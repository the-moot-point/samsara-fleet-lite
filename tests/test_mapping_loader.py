# ruff: noqa: E402
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if "src.mapping_loader" in sys.modules:
    del sys.modules["src.mapping_loader"]
import importlib

ml = importlib.import_module("src.mapping_loader")


@pytest.fixture
def mapping_dir(tmp_path: Path) -> Path:
    tmp_path.joinpath("positions.csv").write_text("Position,TagId\nDriver,123\n")
    tmp_path.joinpath("locations.csv").write_text(
        "Location,Id,Timezone\nHQ,999,\nYard,888,America/Los_Angeles\n"
    )
    tmp_path.joinpath("never_positions.csv").write_text("Position\nIntern\n")
    return tmp_path


def test_load_position_tags(mapping_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ml, "BASE_DIR", mapping_dir)
    assert ml.load_position_tags() == {"Driver": "123"}


def test_load_location_tags_and_timezones(mapping_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ml, "BASE_DIR", mapping_dir)
    assert ml.load_location_tags_and_timezones() == {
        "HQ": {"tag_id": "999", "timezone": "America/Chicago"},
        "Yard": {"tag_id": "888", "timezone": "America/Los_Angeles"},
    }


def test_load_never_positions(mapping_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ml, "BASE_DIR", mapping_dir)
    assert ml.load_never_positions() == {"Intern"}
