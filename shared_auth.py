from __future__ import annotations

import hashlib
import os

ROLE_ADMIN = "Maintenance Manager"
DEFAULT_ADMIN_USERNAME = "maintenance_manager"
AUTH_BRIDGE_KEY = os.getenv("AUTH_BRIDGE_KEY", "ekuruleni-auth-bridge-dev-key")

LEGACY_ROLE_ALIASES = {
    "Admin": ROLE_ADMIN,
    "admin": ROLE_ADMIN,
    "maintenance_manager": ROLE_ADMIN,
    "maintenance manager": ROLE_ADMIN,
    "Technician": "Maintenance Technician",
    "technician": "Maintenance Technician",
    "maintenance_technician": "Maintenance Technician",
    "maintenance technician": "Maintenance Technician",
}


def canonical_role_name(raw_role: str | None) -> str:
    role_name = (raw_role or "").strip()
    if not role_name:
        return ""
    return LEGACY_ROLE_ALIASES.get(role_name, LEGACY_ROLE_ALIASES.get(role_name.lower(), role_name))


def bridge_signature(user_id: str, role: str, bridge_key: str | None = None) -> str:
    secret = (bridge_key or AUTH_BRIDGE_KEY).strip()
    raw = f"{user_id}:{role}:{secret}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
