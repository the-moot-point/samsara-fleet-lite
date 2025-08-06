import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_client_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAMSARA_BEARER_TOKEN", raising=False)
    if "src.samsara_client" in sys.modules:
        del sys.modules["src.samsara_client"]
    with pytest.raises(EnvironmentError):
        import src.samsara_client  # noqa: F401


def test_client_sets_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "abc123"
    monkeypatch.setenv("SAMSARA_BEARER_TOKEN", token)
    if "src.samsara_client" in sys.modules:
        del sys.modules["src.samsara_client"]
    import src.samsara_client as sc

    assert sc.SESSION.headers["Authorization"] == f"Bearer {token}"
