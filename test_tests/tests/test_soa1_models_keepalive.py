import requests

from home_ai.soa1 import models as soa_models


class DummyResponse:
    def __init__(self, status_code=200, data=None):
        self._status = status_code
        self._data = data or {"choices": [{"message": {"content": "ok"}}]}

    def raise_for_status(self):
        if self._status != 200:
            raise requests.HTTPError(f"Status {self._status}")

    def json(self):
        return self._data


def test_call_nemotron_sends_keep_alive(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return DummyResponse()

    monkeypatch.setattr("requests.post", fake_post)

    out = soa_models.call_nemotron("Hello world")

    assert calls, "Expected a requests.post call"
    url, payload, timeout = calls[0]
    assert url.endswith("/api/chat"), f"Unexpected URL: {url}"
    assert payload.get("keep_alive") == -1, f"keep_alive missing or wrong: {payload}"
    assert payload.get("model") == soa_models._ENDPOINTS["nemotron"].model_name
    assert isinstance(out, str)
