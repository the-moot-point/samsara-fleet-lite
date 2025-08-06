import sys
from pathlib import Path
import importlib
import json

import pytest
import requests
import time

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


def _make_response(
    status: int, data: dict | None = None, text: str = ""
) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    if data is not None:
        resp._content = json.dumps(data).encode()
    else:
        resp._content = text.encode()
    resp.headers["Content-Type"] = "application/json"
    return resp


def test_req_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAMSARA_BEARER_TOKEN", "token")
    import src.samsara_client as sc

    importlib.reload(sc)

    monkeypatch.setattr(time, "sleep", lambda _: None)
    responses = [
        _make_response(429, text="too many"),
        _make_response(200, {"ok": True}),
    ]
    calls = {"count": 0}

    def fake_request(
        method: str, url: str, timeout: int = 10, **kw: dict
    ) -> requests.Response:
        resp = responses[calls["count"]]
        calls["count"] += 1
        return resp

    monkeypatch.setattr(sc.SESSION, "request", fake_request)
    assert sc._req("GET", "/foo") == {"ok": True}
    assert calls["count"] == 2


def test_req_retries_on_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAMSARA_BEARER_TOKEN", "token")
    import src.samsara_client as sc

    importlib.reload(sc)

    monkeypatch.setattr(time, "sleep", lambda _: None)
    responses = [
        _make_response(500, text="server error"),
        _make_response(200, {"ok": True}),
    ]
    calls = {"count": 0}

    def fake_request(
        method: str, url: str, timeout: int = 10, **kw: dict
    ) -> requests.Response:
        resp = responses[calls["count"]]
        calls["count"] += 1
        return resp

    monkeypatch.setattr(sc.SESSION, "request", fake_request)
    assert sc._req("GET", "/foo") == {"ok": True}
    assert calls["count"] == 2
