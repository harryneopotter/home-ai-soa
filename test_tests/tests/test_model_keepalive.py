import requests
import pytest

from home_ai.soa1.model import ModelClient


class DummyResponse:
    def __init__(self, status_code=200, data=None):
        self._status = status_code
        self._data = data or {"message": {"content": "ok"}}

    def raise_for_status(self):
        if self._status != 200:
            raise requests.HTTPError(f"Status {self._status}")

    def json(self):
        return self._data


def test_modelclient_chat_sends_keep_alive(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return DummyResponse()

    monkeypatch.setattr("requests.post", fake_post)

    m = ModelClient(config_path="config.yaml")
    out = m.chat("system prompt", [{"role": "user", "content": "hi"}])

    assert calls, "Expected a requests.post call"
    url, payload, timeout = calls[0]
    assert url.endswith("/api/chat")
    assert payload.get("keep_alive") == -1
    assert payload.get("model") == m.model_name
    assert isinstance(out, str)
