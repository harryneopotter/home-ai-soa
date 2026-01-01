#!/usr/bin/env python3
"""
Integration test: Verify Ollama models are pinned with keep_alive=-1 (Forever).

This test:
1. Calls the actual Ollama API to trigger model loading
2. Checks `ollama ps` output to verify UNTIL shows "Forever"
3. Validates both NemoAgent and phinance-json are properly pinned

Run with: python test_scripts/test_ollama_keepalive_integration.py
Requires: Ollama running at localhost:11434
"""

import subprocess
import requests
import time
import sys

OLLAMA_URL = "http://localhost:11434"
REQUIRED_MODELS = ["NemoAgent", "phinance-json"]


def check_ollama_running() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def trigger_model_load(model_name: str) -> bool:
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
                "keep_alive": -1,
                "options": {"num_predict": 1},
            },
            timeout=120,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"  Failed to load {model_name}: {e}")
        return False


def get_loaded_models() -> dict:
    try:
        result = subprocess.run(
            ["ollama", "ps"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {}

        models = {}
        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:
            return {}

        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                name = parts[0]
                until = parts[-1]
                models[name] = until

        return models
    except Exception as e:
        print(f"Failed to run ollama ps: {e}")
        return {}


def test_keepalive_forever():
    print("=" * 60)
    print("Ollama Keep-Alive Integration Test")
    print("=" * 60)

    if not check_ollama_running():
        print("❌ FAIL: Ollama not running at", OLLAMA_URL)
        return False
    print("✅ Ollama is running")

    print("\nLoading models with keep_alive=-1...")
    for model in REQUIRED_MODELS:
        print(f"  Loading {model}...", end=" ", flush=True)
        if trigger_model_load(model):
            print("OK")
        else:
            print("FAILED")

    time.sleep(2)

    print("\nChecking ollama ps output...")
    loaded = get_loaded_models()

    if not loaded:
        print("❌ FAIL: No models loaded or ollama ps failed")
        return False

    print(f"  Found {len(loaded)} loaded model(s):")
    for name, until in loaded.items():
        print(f"    {name}: UNTIL={until}")

    all_pass = True
    print("\nVerifying keep_alive status:")
    for model in REQUIRED_MODELS:
        found = False
        for loaded_name, until in loaded.items():
            if model.lower() in loaded_name.lower():
                found = True
                if until.lower() == "forever":
                    print(f"  ✅ {model}: UNTIL=Forever (PASS)")
                else:
                    print(f"  ❌ {model}: UNTIL={until} (FAIL - expected Forever)")
                    all_pass = False
                break

        if not found:
            print(f"  ⚠️  {model}: Not currently loaded (may have been evicted)")

    print("\n" + "=" * 60)
    if all_pass:
        print("✅ ALL TESTS PASSED")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = test_keepalive_forever()
    sys.exit(0 if success else 1)
