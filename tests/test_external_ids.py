import importlib


def test_normalize_external_ids(monkeypatch):
    monkeypatch.setenv("SAMSARA_BEARER_TOKEN", "token")
    import src.samsara_client as sc

    importlib.reload(sc)

    payload = {
        "externalIds": {
            "EncompassId": "8199",
            "encompass_id": "8199",
            "OTHER": "1",
        }
    }
    sc._normalize_external_ids(payload)
    assert payload["externalIds"] == {"encompassId": "8199", "OTHER": "1"}


def test_req_normalizes_external_ids(monkeypatch):
    monkeypatch.setenv("SAMSARA_BEARER_TOKEN", "token")
    import src.samsara_client as sc

    importlib.reload(sc)

    class DummyResp:
        status_code = 200

        def json(self):
            return {}

    captured = {}

    def fake_request(method, url, timeout=10, **kw):
        captured["json"] = kw.get("json")
        return DummyResp()

    monkeypatch.setattr(sc.SESSION, "request", fake_request)

    sc._req(
        "PATCH",
        "/fleet/drivers/1",
        json={"externalIds": {"EncompassId": "8199", "encompass_id": "8199"}},
    )

    assert captured["json"]["externalIds"] == {"encompassId": "8199"}

