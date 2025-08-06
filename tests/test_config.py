import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_config_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAMSARA_BEARER_TOKEN", raising=False)
    if "config" in sys.modules:
        del sys.modules["config"]
    with pytest.raises(EnvironmentError):
        import config  # noqa: F401


def test_config_loads_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAMSARA_BEARER_TOKEN", "token123")
    if "config" in sys.modules:
        del sys.modules["config"]
    import config

    assert config.settings.api_token == "token123"
