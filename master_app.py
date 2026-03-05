from __future__ import annotations
"""Master integration portal entrypoint.

How to add another app into this integration:
1) Define its script/path and port constants near the existing maintenance constants.
2) Add app config values to `app.config` so route modules can build links/health checks.
3) Extend `run_all_apps()` and `orchestrator_status()` to start/report that app.
4) Add/extend auth route bridge handling in `auth_routes.py` (`/auth/open/<app_key>`).

This file should remain the lightweight orchestrator for process startup, status,
and root-level redirects.
"""

import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, request, url_for

try:
    from auth_portal.auth_routes import auth_bp
    from auth_portal.integration_policy import POLICY_VERSION, get_policy_apps
except ModuleNotFoundError:
    from auth_routes import auth_bp
    from integration_policy import POLICY_VERSION, get_policy_apps


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
MAINTENANCE_SCRIPT = WORKSPACE_ROOT / "fake data" / "joburg_water_flask_app" / "app.py"
STATIC_DIR = WORKSPACE_ROOT / "fake data" / "joburg_water_flask_app" / "static"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

MASTER_PORT = int(os.getenv("MASTER_PORT", "5000"))
MAINTENANCE_PORT = int(os.getenv("MAINTENANCE_PORT", "5001"))

# For future apps, follow the same pattern used for maintenance:
# - APP_NAME_SCRIPT path
# - APP_NAME_PORT
# - app.config["APP_NAME_BASE_URL"]

app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(TEMPLATE_DIR))
app.secret_key = os.getenv("AUTH_PORTAL_SECRET_KEY", "ekuruleni-auth-portal-dev-secret")
app.config["MAINTENANCE_APP_BASE_URL"] = f"http://127.0.0.1:{MAINTENANCE_PORT}"
app.config["MAINTENANCE_APP_PORT"] = MAINTENANCE_PORT
app.config["MAINTENANCE_SCRIPT_PATH"] = str(MAINTENANCE_SCRIPT)
app.config["WORKSPACE_ROOT"] = str(WORKSPACE_ROOT)
app.config["INTEGRATED_APPS"] = get_policy_apps(app.config)
app.config["INTEGRATION_POLICY_VERSION"] = POLICY_VERSION
app.register_blueprint(auth_bp)


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


PROCESS_REGISTRY: dict[str, subprocess.Popen[Any]] = {}


def _start_process(key: str, command: list[str], port: int) -> dict[str, Any]:
    if _is_port_open(port):
        return {"key": key, "started": False, "status": "already-running", "port": port}

    existing = PROCESS_REGISTRY.get(key)
    if existing and existing.poll() is None:
        return {"key": key, "started": False, "status": "running-in-registry", "port": port}

    env = os.environ.copy()
    env["PORT"] = str(port)
    process = subprocess.Popen(command, cwd=str(WORKSPACE_ROOT), env=env)
    PROCESS_REGISTRY[key] = process
    return {"key": key, "started": True, "status": "started", "pid": process.pid, "port": port}


@app.route("/")
def root() -> Any:
    return redirect(url_for("auth.login"))


@app.route("/report-incident")
def report_incident_proxy() -> Any:
    return redirect(f"{app.config['MAINTENANCE_APP_BASE_URL']}/report-incident")


@app.route("/orchestrator/run-all-apps", methods=["POST", "GET"])
def run_all_apps() -> Any:
    integrated_apps = get_policy_apps(app.config)
    app.config["INTEGRATED_APPS"] = integrated_apps

    started_apps: list[dict[str, Any]] = []
    for integrated_app in integrated_apps:
        if not bool(integrated_app.get("enabled")) or not bool(integrated_app.get("auto_start")):
            continue

        key = str(integrated_app.get("key") or "").strip()
        script_path = str(integrated_app.get("script_path") or "").strip()
        port = integrated_app.get("port")
        if not key or not script_path or not isinstance(port, int):
            continue

        start_result = _start_process(
            key=key,
            command=[sys.executable, script_path],
            port=port,
        )
        started_apps.append(
            {
                **start_result,
                "name": str(integrated_app.get("name") or key),
                "url": str(integrated_app.get("base_url") or f"http://127.0.0.1:{port}"),
            }
        )

    return jsonify(
        {
            "ok": True,
            "policy_version": app.config.get("INTEGRATION_POLICY_VERSION", POLICY_VERSION),
            "master": {
                "key": "master-auth-portal",
                "status": "running",
                "port": MASTER_PORT,
                "url": f"http://127.0.0.1:{MASTER_PORT}",
            },
            "apps": started_apps,
            "message": "Apps orchestration executed using policy-controlled startup rules.",
        }
    )


@app.route("/orchestrator/status", methods=["GET"])
def orchestrator_status() -> Any:
    integrated_apps = get_policy_apps(app.config)
    app.config["INTEGRATED_APPS"] = integrated_apps

    app_status_rows: list[dict[str, Any]] = []
    for integrated_app in integrated_apps:
        port = integrated_app.get("port")
        running = _is_port_open(port) if isinstance(port, int) else False
        app_status_rows.append(
            {
                "key": integrated_app.get("key"),
                "name": integrated_app.get("name"),
                "enabled": bool(integrated_app.get("enabled")),
                "rollout_wave": integrated_app.get("rollout_wave"),
                "running": running,
                "port": port,
                "url": integrated_app.get("base_url") or (f"http://127.0.0.1:{port}" if isinstance(port, int) else ""),
            }
        )

    return jsonify(
        {
            "ok": True,
            "policy_version": app.config.get("INTEGRATION_POLICY_VERSION", POLICY_VERSION),
            "master": {
                "running": True,
                "port": MASTER_PORT,
                "url": f"http://127.0.0.1:{MASTER_PORT}",
            },
            "apps": app_status_rows,
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=MASTER_PORT, use_reloader=False)
