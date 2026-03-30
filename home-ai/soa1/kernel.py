from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger("kernel")


@dataclass(frozen=True)
class UserContext:
    user_id: str
    role: str
    vault_path: Path
    is_isolated: bool = True


class SOA1Kernel:
    """
    Kernel for SOA1: manages identity, user context, and scoped storage paths.
    """

    def __init__(self, manifest_path: Optional[str] = None) -> None:
        self._repo_root = Path(__file__).resolve().parents[2]
        self._manifest_path = self._resolve_manifest_path(manifest_path)
        self.manifest: Dict[str, Any] = self._load_manifest(self._manifest_path)
        self.active_user: Optional[UserContext] = None
        self.base_vault_dir = self._repo_root / "vaults"

    def _resolve_manifest_path(self, manifest_path: Optional[str]) -> Path:
        if manifest_path:
            return Path(manifest_path).expanduser().resolve()

        env_path = os.getenv("SOA1_MANIFEST_PATH")
        if env_path:
            return Path(env_path).expanduser().resolve()

        candidates = [
            self._repo_root / "WHOAMI.json",
            self._repo_root / "plan" / "future-plans" / "feb" / "WHOAMI.json",
            self._repo_root
            / "plan"
            / "future-plans"
            / "feb"
            / "WHOAMI.template.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        return self._repo_root / "WHOAMI.json"

    def _load_manifest(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            logger.error("Manifest missing at %s", path)
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            logger.error("Failed to read manifest %s: %s", path, exc)
            return {}

    def reload_manifest(self) -> None:
        self.manifest = self._load_manifest(self._manifest_path)

    def set_user_context(self, user_id: str) -> None:
        if not user_id:
            raise ValueError("user_id is required to set kernel context")

        user_info = self._get_user_info(user_id)
        vault_path = self.base_vault_dir / user_id
        vault_path.mkdir(parents=True, exist_ok=True)

        self.active_user = UserContext(
            user_id=user_id,
            role=user_info.get("role", "user"),
            vault_path=vault_path,
            is_isolated=bool(user_info.get("context_isolated", True)),
        )
        logger.info("Kernel context switched to user: %s", user_id)

    def update_user_profile(
        self,
        user_id: str,
        traits: Optional[List[str]] = None,
        notes: Optional[List[str]] = None,
    ) -> None:
        updated = False
        users = self.manifest.get("users", {})

        primary = users.get("primary", {})
        if primary.get("id") == user_id:
            if traits is not None:
                primary["traits"] = traits
            if notes is not None:
                primary["sensory_notes"] = notes
            updated = True

        if not updated:
            for member in users.get("family", []) or []:
                if member.get("id") == user_id:
                    if traits is not None:
                        member["traits"] = traits
                    if notes is not None:
                        member["sensory_notes"] = notes
                    updated = True
                    break

        if updated:
            self._save_manifest()
            if self.active_user and self.active_user.user_id == user_id:
                self.set_user_context(user_id)
            logger.info("Profile updated for user: %s", user_id)
        else:
            logger.warning("User %s not found to update profile", user_id)

    def register_user(
        self,
        user_id: str,
        role: str = "user",
        traits: Optional[List[str]] = None,
    ) -> None:
        if not user_id:
            raise ValueError("user_id is required to register a user")

        users = self.manifest.setdefault("users", {})
        family = users.setdefault("family", [])

        if any(member.get("id") == user_id for member in family):
            logger.info("User already registered: %s", user_id)
            return

        family.append(
            {
                "id": user_id,
                "role": role,
                "traits": traits or [],
                "sensory_notes": [],
                "context_isolated": True,
            }
        )
        self._save_manifest()
        logger.info("New user registered: %s", user_id)

    def _save_manifest(self) -> None:
        try:
            with self._manifest_path.open("w", encoding="utf-8") as handle:
                json.dump(self.manifest, handle, indent=2)
        except Exception as exc:
            logger.error("Failed to save manifest: %s", exc)

    def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        users = self.manifest.get("users", {})
        primary = users.get("primary", {})
        if user_id == primary.get("id"):
            return primary

        for member in users.get("family", []) or []:
            if member.get("id") == user_id:
                return member

        return {"role": "guest", "context_isolated": True}

    def get_identity_prompt(self) -> str:
        if not self.active_user:
            return "Identity system offline. Please authenticate."

        entity = self.manifest.get("entity", {})
        constraints = self.manifest.get("operational_constraints", {})
        users = self.manifest.get("users", {})
        family = users.get("family", []) or []

        prompt_lines = [
            f"You are {entity.get('name', 'SOA1')} (v{entity.get('version', '0.0')}).",
            f"NATURE: {entity.get('nature', 'Local assistant')}.",
        ]

        host = entity.get("host_machine", {})
        if host:
            prompt_lines.append(
                "HARDWARE: "
                f"{host.get('gpu_config', 'unknown GPU')} with "
                f"{host.get('ram', 'unknown RAM')} RAM."
            )

        if constraints:
            cloud_allowed = constraints.get("cloud_allowed", False)
            prompt_lines.append(
                "CONSTRAINTS: Cloud is "
                + ("ALLOWED" if cloud_allowed else "FORBIDDEN")
                + ". Data stays local."
            )

        capabilities = [
            cap
            for cap in self.manifest.get("capabilities", []) or []
            if cap.get("status") == "active"
        ]
        if capabilities:
            prompt_lines.append("CAPABILITIES:")
            for cap in capabilities:
                cap_id = cap.get("id", "unknown")
                desc = cap.get("description", "")
                prompt_lines.append(f"- {cap_id}: {desc}".strip())

        prompt_lines.append(
            f"ACTIVE USER: {self.active_user.user_id} ({self.active_user.role})."
        )

        user_info = self._get_user_info(self.active_user.user_id)
        traits = user_info.get("traits") or []
        notes = user_info.get("sensory_notes") or []

        if traits:
            prompt_lines.append(f"USER TRAITS: {', '.join(traits)}.")
        if notes:
            prompt_lines.append(f"SENSORY NOTES: {', '.join(notes)}.")

        if family:
            family_ids = [member.get("id", "unknown") for member in family]
            prompt_lines.append(f"KNOWN FAMILY: {', '.join(family_ids)}.")

        return "\n".join(prompt_lines)

    def get_scoped_db_path(self, db_name: str) -> Path:
        if not self.active_user:
            raise PermissionError("No user context set.")
        return self.active_user.vault_path / db_name

    def get_capability(self, cap_id: str) -> Dict[str, Any]:
        for cap in self.manifest.get("capabilities", []) or []:
            if cap.get("id") == cap_id and cap.get("status") == "active":
                return cap
        raise ValueError(f"Capability '{cap_id}' not found or inactive.")

    def route_to_specialist(self, cap_id: str) -> str:
        cap = self.get_capability(cap_id)
        return cap.get("model", "default_specialist")


kernel = SOA1Kernel()
