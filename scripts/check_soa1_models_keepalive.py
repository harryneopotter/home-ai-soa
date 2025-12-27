#!/usr/bin/env python3
"""Smoke-check: ensure call_nemotron uses /api/chat with keep_alive:-1"""

import requests

from home_ai.soa1 import models as soa_models


calls = []


def fake_post(url, json, timeout):
    calls.append((url, json, timeout))

    class R:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    return R()


if __name__ == "__main__":
    orig_post = requests.post
    try:
        requests.post = fake_post
        out = soa_models.call_nemotron("Hello world")
        print("call_nemotron returned:", out[:120])

        if not calls:
            print("ERROR: no HTTP calls recorded")
            raise SystemExit(2)

        url, payload, timeout = calls[0]
        print("Recorded call URL:", url)
        print("Recorded payload keep_alive:", payload.get("keep_alive"))
        print("Recorded model:", payload.get("model"))

        ok = url.endswith("/api/chat") and payload.get("keep_alive") == -1
        if ok:
            print("OK: call_nemotron sends keep_alive:-1 to /api/chat")
            raise SystemExit(0)
        else:
            print("FAIL: unexpected call shape")
            raise SystemExit(1)
    finally:
        requests.post = orig_post
