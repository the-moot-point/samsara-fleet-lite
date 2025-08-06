import pandas as pd
from pathlib import Path
from typing import Mapping, Set

BASE_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def load_position_tags() -> Mapping[str, str]:
    df = _read_csv(BASE_DIR / "positions.csv")
    return dict(zip(df["Position"], df["TagId"]))


def load_location_tags_and_timezones() -> dict[str, dict[str, str]]:
    """
    Returns mapping:
        {
          "Abilene": {"tag_id": "2762144", "timezone": "America/Chicago"},
          ...
        }
    """
    df = pd.read_csv(BASE_DIR / "locations.csv", dtype=str).fillna("")
    df.columns = df.columns.str.lower()
    return {
        row["location"].strip(): {
            "tag_id": row["id"].strip(),
            "timezone": row["timezone"].strip() or "America/Chicago",
        }
        for _, row in df.iterrows()
    }


def load_never_positions() -> Set[str]:
    df = _read_csv(BASE_DIR / "never_positions.csv")
    return set(df["Position"])
