from __future__ import annotations

"""Central policy and rollout controls for integrated applications.

This module is the single source of truth for:
- Which apps are integrated with the auth portal
- Which roles can open each app
- Which apps are active in the current rollout wave
- Which apps are allowed to auto-start from the orchestrator

When adding a new app, update `BASE_INTEGRATED_APPS` first, then wire runtime
config keys in `master_app.py` and app opening logic in `auth_routes.py`.
"""

from copy import deepcopy
from typing import Any, Mapping

POLICY_VERSION = "1.0"

BASE_INTEGRATED_APPS: list[dict[str, Any]] = [
    {
        "key": "maintenance",
        "name": "Maintenance Management System",
        "description": "Operational maintenance workspace for incidents, dispatch, resources, and field execution.",
        "theme": "g",
        "enabled": True,
        "status": "Live",
        "rollout_wave": "wave-1",
        "auto_start": True,
        "requires_bridge": True,
        "access_roles": ["*"],
        "base_url_config_key": "MAINTENANCE_APP_BASE_URL",
        "port_config_key": "MAINTENANCE_APP_PORT",
        "script_path_config_key": "MAINTENANCE_SCRIPT_PATH",
    },
    {
        "key": "finance",
        "name": "Finance Management System",
        "description": "Budget, spend, and financial controls portal.",
        "theme": "b",
        "enabled": False,
        "status": "Planned",
        "rollout_wave": "wave-2",
        "auto_start": False,
        "requires_bridge": True,
        "access_roles": ["Maintenance Manager", "Inventory Manager"],
        "base_url_config_key": "FINANCE_APP_BASE_URL",
        "port_config_key": "FINANCE_APP_PORT",
        "script_path_config_key": "FINANCE_SCRIPT_PATH",
    },
    {
        "key": "registration",
        "name": "Registration & Records System",
        "description": "Citizen registration, records, and verification operations.",
        "theme": "y",
        "enabled": False,
        "status": "Planned",
        "rollout_wave": "wave-3",
        "auto_start": False,
        "requires_bridge": True,
        "access_roles": ["Maintenance Manager"],
        "base_url_config_key": "REGISTRATION_APP_BASE_URL",
        "port_config_key": "REGISTRATION_APP_PORT",
        "script_path_config_key": "REGISTRATION_SCRIPT_PATH",
    },
]


def get_policy_apps(config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    apps = deepcopy(BASE_INTEGRATED_APPS)
    if not config:
        return apps

    for app in apps:
        base_key = str(app.get("base_url_config_key") or "").strip()
        port_key = str(app.get("port_config_key") or "").strip()
        script_key = str(app.get("script_path_config_key") or "").strip()
        app["base_url"] = str(config.get(base_key, "") or "").strip().rstrip("/") if base_key else ""
        app["script_path"] = str(config.get(script_key, "") or "").strip() if script_key else ""

        if port_key:
            raw_port = config.get(port_key)
            try:
                app["port"] = int(str(raw_port)) if raw_port is not None and str(raw_port).strip() else None
            except (TypeError, ValueError):
                app["port"] = None
        else:
            app["port"] = None

    return apps


def get_policy_app(app_key: str, config: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    normalized = (app_key or "").strip().lower()
    for app in get_policy_apps(config):
        if str(app.get("key") or "").strip().lower() == normalized:
            return app
    return None


def user_has_app_access(app: Mapping[str, Any], role: str | None) -> bool:
    if not bool(app.get("enabled")):
        return False

    allowed_roles = [str(value).strip() for value in (app.get("access_roles") or []) if str(value).strip()]
    if not allowed_roles:
        return False
    if "*" in allowed_roles:
        return True

    current_role = (role or "").strip()
    return current_role in allowed_roles
