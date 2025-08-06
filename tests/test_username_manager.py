import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.username_manager import UsernameManager


def test_batching(tmp_path: Path) -> None:
    csv = tmp_path / "usernames.csv"
    manager = UsernameManager(csv_path=csv)

    for i in range(9):
        manager.add_username(f"user{i}")

    df = pd.read_csv(csv)
    assert df.empty

    manager.add_username("user9")
    df = pd.read_csv(csv)
    assert sorted(df["username"]) == [f"user{i}" for i in range(10)]


def test_flush_on_exit(tmp_path: Path) -> None:
    csv = tmp_path / "usernames.csv"
    script = f"""import sys\nfrom pathlib import Path\nsys.path.insert(0, {str(ROOT)!r})\nfrom src.username_manager import UsernameManager\ncsv = Path({str(csv)!r})\nmanager = UsernameManager(csv_path=csv)\nmanager.add_username('shutdownuser')\n"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )

    df = pd.read_csv(csv)
    assert "shutdownuser" in df["username"].tolist()


def test_persistence(tmp_path: Path) -> None:
    csv = tmp_path / "usernames.csv"
    manager = UsernameManager(csv_path=csv)

    username = manager.make_unique("alice")
    manager.flush()

    new_manager = UsernameManager(csv_path=csv)
    assert new_manager.exists(username)
