from soa1.kernel import kernel
import json
import os

def verify_appliance_logic():
    print("--- 1. Testing User Registration ---")
    kernel.register_user("sachin_test", role="admin", traits=["Shinobi Mode", "ADHD"])
    
    with open("WHOAMI.json", "r") as f:
        data = json.load(f)
        found = any(u["id"] == "sachin_test" for u in data["users"]["family"])
        print(f"User in WHOAMI.json: {'PASS' if found else 'FAIL'}")

    print("\n--- 2. Testing Profile Update ---")
    kernel.update_user_profile("sachin_test", notes=["Anosmia detected"])
    
    with open("WHOAMI.json", "r") as f:
        data = json.load(f)
        user = next(u for u in data["users"]["family"] if u["id"] == "sachin_test")
        print(f"Notes updated in JSON: {'PASS' if 'Anosmia detected' in user['sensory_notes'] else 'FAIL'}")

    print("\n--- 3. Testing Identity Prompt Generation ---")
    kernel.set_user_context("sachin_test")
    prompt = kernel.get_identity_prompt()
    print("Generated Prompt Preview:")
    print("-" * 30)
    print(prompt)
    print("-" * 30)
    
    if "Shinobi Mode" in prompt and "Anosmia detected" in prompt:
        print("Prompt Verification: PASS")
    else:
        print("Prompt Verification: FAIL")

if __name__ == "__main__":
    # Ensure we are in the right dir
    verify_appliance_logic()
