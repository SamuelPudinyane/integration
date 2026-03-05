from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, request, url_for

try:
    from auth_portal.auth_routes import auth_bp
except ModuleNotFoundError:
    from auth_routes import auth_bp


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
MAINTENANCE_SCRIPT = WORKSPACE_ROOT / "fake data" / "joburg_water_flask_app" / "app.py"
STATIC_DIR = WORKSPACE_ROOT / "fake data" / "joburg_water_flask_app" / "static"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

MASTER_PORT = int(os.getenv("MASTER_PORT", "5000"))
MAINTENANCE_PORT = int(os.getenv("MAINTENANCE_PORT", "5001"))

app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(TEMPLATE_DIR))
app.secret_key = os.getenv("AUTH_PORTAL_SECRET_KEY", "ekuruleni-auth-portal-dev-secret")
app.config["MAINTENANCE_APP_BASE_URL"] = f"http://127.0.0.1:{MAINTENANCE_PORT}"
app.config["MAINTENANCE_APP_PORT"] = MAINTENANCE_PORT
app.config["MAINTENANCE_SCRIPT_PATH"] = str(MAINTENANCE_SCRIPT)
app.config["WORKSPACE_ROOT"] = str(WORKSPACE_ROOT)
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
    maintenance_result = _start_process(
        key="maintenance",
        command=[sys.executable, str(MAINTENANCE_SCRIPT)],
        port=MAINTENANCE_PORT,
    )

    return jsonify(
        {
            "ok": True,
            "master": {
                "key": "master-auth-portal",
                "status": "running",
                "port": MASTER_PORT,
                "url": f"http://127.0.0.1:{MASTER_PORT}",
            },
            "apps": [
                {
                    **maintenance_result,
                    "url": f"http://127.0.0.1:{MAINTENANCE_PORT}",
                }
            ],
            "message": "Apps orchestration executed. Maintenance app is ensured on its dedicated port.",
        }
    )


@app.route("/orchestrator/status", methods=["GET"])
def orchestrator_status() -> Any:
    maintenance_up = _is_port_open(MAINTENANCE_PORT)
    return jsonify(
        {
            "ok": True,
            "master": {
                "running": True,
                "port": MASTER_PORT,
                "url": f"http://127.0.0.1:{MASTER_PORT}",
            },
            "maintenance": {
                "running": maintenance_up,
                "port": MAINTENANCE_PORT,
                "url": f"http://127.0.0.1:{MAINTENANCE_PORT}",
            },
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=MASTER_PORT, use_reloader=False)
