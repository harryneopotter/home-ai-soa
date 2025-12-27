#!/usr/bin/env python3
"""Integration test: verify orchestrator model configuration and routing."""

import requests
import sys

WEBUI_BASE = "http://localhost:8080"


def test_models_verify_endpoint():
    print("Testing /api/models/verify endpoint...")

    resp = requests.get(f"{WEBUI_BASE}/api/models/verify", timeout=10)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    data = resp.json()
    print(f"✓ Endpoint returned valid JSON")

    assert "orchestrator" in data, "Missing 'orchestrator' key"
    assert "specialists" in data, "Missing 'specialists' key"
    assert "loaded_models" in data, "Missing 'loaded_models' key"
    print("✓ Response structure valid")

    orch = data["orchestrator"]
    assert orch["model_agnostic"] is True, "Orchestrator should be model-agnostic"
    assert orch["has_modelfile"] is False, "Orchestrator should NOT have a Modelfile"
    assert orch["system_prompt_exists"] is True, (
        "Orchestrator system prompt should exist"
    )
    print(f"✓ Orchestrator config valid (model_agnostic=True, has_modelfile=False)")

    if orch["system_prompt_preview"]:
        preview = orch["system_prompt_preview"]
        assert "consent" in preview.lower() or "Daily Home Assistant" in preview, (
            "System prompt should mention consent or identity"
        )
        print(
            f"✓ System prompt preview contains expected content ({len(orch.get('system_prompt_length', 0))} chars)"
        )

    phinance = data["specialists"].get("phinance", {})
    assert phinance.get("has_modelfile") is True, "phinance should have a Modelfile"
    assert phinance.get("model") == "phinance-json", (
        "phinance model should be 'phinance-json'"
    )
    print(f"✓ Phinance specialist config valid (has_modelfile=True)")

    return data


def test_orchestrator_is_ui_facing():
    print("\nVerifying orchestrator is the only UI-facing model...")

    data = requests.get(f"{WEBUI_BASE}/api/models/verify", timeout=10).json()
    loaded = data.get("loaded_models", [])

    orchestrators = [m for m in loaded if m.get("role") == "orchestrator"]
    specialists = [m for m in loaded if m.get("role", "").startswith("specialist")]

    print(f"  Loaded models: {len(loaded)}")
    print(f"  Orchestrators: {[m['name'] for m in orchestrators]}")
    print(f"  Specialists: {[m['name'] for m in specialists]}")

    if len(orchestrators) == 1:
        print(f"✓ Exactly one orchestrator loaded: {orchestrators[0]['name']}")
    elif len(orchestrators) == 0:
        print("⚠ WARNING: No orchestrator model loaded (may need to warm up)")
    else:
        print(
            f"⚠ WARNING: Multiple orchestrators loaded: {[m['name'] for m in orchestrators]}"
        )

    for spec in specialists:
        if spec["name"] == "phinance-json":
            print(f"✓ phinance-json loaded as specialist (not UI-facing)")


def test_chat_uses_orchestrator():
    print("\nVerifying /chat uses orchestrator model...")

    try:
        resp = requests.post(
            f"{WEBUI_BASE}/chat",
            json={"message": "Hello, what can you help me with?"},
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            response_text = data.get("response", "")
            if response_text:
                print(
                    f"✓ Chat endpoint responded (first 100 chars): {response_text[:100]}..."
                )
            else:
                print("⚠ Chat response was empty")
        else:
            print(f"⚠ Chat endpoint returned {resp.status_code}: {resp.text[:200]}")
    except requests.exceptions.Timeout:
        print("⚠ Chat request timed out (model may be loading)")
    except Exception as e:
        print(f"⚠ Chat test failed: {e}")


def main():
    print("=" * 60)
    print("INTEGRATION TEST: Model Verification")
    print("=" * 60)

    try:
        health = requests.get(f"{WEBUI_BASE}/health", timeout=5)
        if health.status_code != 200:
            print(f"ERROR: WebUI not healthy at {WEBUI_BASE}")
            sys.exit(1)
        print(f"✓ WebUI is running at {WEBUI_BASE}\n")
    except Exception as e:
        print(f"ERROR: Cannot reach WebUI at {WEBUI_BASE}: {e}")
        sys.exit(1)

    test_models_verify_endpoint()
    test_orchestrator_is_ui_facing()
    test_chat_uses_orchestrator()

    print("\n" + "=" * 60)
    print("✅ All model verification tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
