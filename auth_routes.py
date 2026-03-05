from __future__ import annotations
"""Auth portal routes and integration bridge helpers.

Developer extension guide (adding another integrated app):
1) Add a card entry in `_system_cards()` with a unique `key` and `has_access` policy.
2) Add app-specific URL/signature helpers similar to maintenance bridge helpers.
3) Extend `open_internal_app()` to route the new `app_key` to the target app.
4) If the app needs auto-start, add health-check + bootstrap logic like
    `_is_maintenance_online()` and `_ensure_maintenance_online()`.

Keep this file focused on portal-level routing/orchestration and keep app-specific
business logic inside the target app's own codebase.
"""

import os
import socket
import subprocess
import sys
import time
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

try:
    from auth_portal.auth_backend import (
        DEFAULT_ADMIN_USERNAME,
        authenticate_user,
        get_user_by_id,
        read_l1_l3_process_hierarchy,
        read_process_steps,
    )
    from auth_portal.shared_auth import AUTH_BRIDGE_KEY, bridge_signature
except ModuleNotFoundError:
    from auth_backend import DEFAULT_ADMIN_USERNAME, authenticate_user, get_user_by_id, read_l1_l3_process_hierarchy, read_process_steps
    from shared_auth import AUTH_BRIDGE_KEY, bridge_signature


auth_bp = Blueprint("auth", __name__)


def _maintenance_base_url() -> str:
    configured = str(current_app.config.get("MAINTENANCE_APP_BASE_URL", "http://127.0.0.1:5001")).strip()
    return configured.rstrip("/")


def _is_maintenance_online() -> bool:
    port = int(str(current_app.config.get("MAINTENANCE_APP_PORT", "5001")))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _ensure_maintenance_online() -> bool:
    if _is_maintenance_online():
        return True

    script_path = str(current_app.config.get("MAINTENANCE_SCRIPT_PATH", "")).strip()
    workspace_root = str(current_app.config.get("WORKSPACE_ROOT", "")).strip()
    port = int(str(current_app.config.get("MAINTENANCE_APP_PORT", "5001")))

    if not script_path:
        return False

    process = current_app.config.get("MAINTENANCE_PROCESS")
    if not process or process.poll() is not None:
        env = os.environ.copy()
        env["PORT"] = str(port)
        process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=workspace_root if workspace_root else str(Path(script_path).resolve().parent),
            env=env,
        )
        current_app.config["MAINTENANCE_PROCESS"] = process

    for _ in range(15):
        if _is_maintenance_online():
            return True
        time.sleep(0.25)
    return _is_maintenance_online()


def _bridge_signature(user_id: str, role: str) -> str:
    return bridge_signature(user_id, role, AUTH_BRIDGE_KEY)


def _maintenance_bridge_url(user_id: str, role: str) -> str:
    params = urlencode(
        {
            "user_id": user_id,
            "role": role,
            "sig": _bridge_signature(user_id, role),
        }
    )
    return f"{_maintenance_base_url()}/auth/bridge-login?{params}"


def _require_login(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _system_cards() -> list[dict[str, str | bool]]:
    # Add new integrated applications here so they appear on the master landing page.
    # `key` must match what `open_internal_app()` expects in `/auth/open/<app_key>`.
    return [
        {
            "key": "maintenance",
            "name": "Maintenance Management System",
            "description": "Operational maintenance workspace for incidents, dispatch, resources, and field execution.",
            "status": "Live",
            "theme": "g",
            "has_access": True,
        },
        {
            "key": "finance",
            "name": "Finance Management System",
            "description": "Budget, spend, and financial controls portal.",
            "status": "Restricted",
            "theme": "b",
            "has_access": False,
        },
        {
            "key": "registration",
            "name": "Registration & Records System",
            "description": "Citizen registration, records, and verification operations.",
            "status": "Restricted",
            "theme": "y",
            "has_access": False,
        },
    ]


def _hierarchy_data() -> dict[str, object]:
    try:
        hierarchy = read_l1_l3_process_hierarchy()
        process_data = read_process_steps()
        return {
            "title": "L1-L3 Process Hierarchy",
            "roots": hierarchy.get("roots", []),
            "relationships": [],
            "total_departments": 0,
            "source_table": "",
            "source_file": hierarchy.get("source_file", ""),
            "level_counts": hierarchy.get("level_counts", {"l1": 0, "l2": 0, "l3": 0}),
            "process_tables": process_data.get("tables", []),
            "process_steps": process_data.get("records", []),
            "total_process_steps": int(process_data.get("total_steps", 0) or 0),
            "load_error": hierarchy.get("load_error", ""),
        }
    except Exception as exc:
        return {
            "title": "L1-L3 Process Hierarchy",
            "roots": [],
            "relationships": [],
            "total_departments": 0,
            "source_table": "public.ref_organization_unit",
            "source_file": "",
            "level_counts": {"l1": 0, "l2": 0, "l3": 0},
            "process_tables": [],
            "process_steps": [],
            "total_process_steps": 0,
            "load_error": str(exc),
        }


@auth_bp.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        next_url = request.form.get("next", "")

        matched, error_message = authenticate_user(username, password)
        if error_message:
            flash(error_message, "danger" if "required" not in error_message.lower() else "warning")
            return render_template(
                "auth/login.html",
                admin_username=DEFAULT_ADMIN_USERNAME,
                next_url=next_url,
                community_report_url=f"{_maintenance_base_url()}/report-incident",
            )

        session["user_id"] = matched.get("id")
        session["role"] = matched.get("role")
        flash(f"Welcome {matched.get('username')} ({matched.get('role')}).", "success")
        return redirect(url_for("auth.master_landing"))

    return render_template(
        "auth/login.html",
        admin_username=DEFAULT_ADMIN_USERNAME,
        next_url=request.args.get("next", ""),
        community_report_url=f"{_maintenance_base_url()}/report-incident",
    )


@auth_bp.route("/auth/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/auth/master")
@_require_login
def master_landing():
    user = get_user_by_id(session.get("user_id"))
    return render_template(
        "auth/sample10.html",
        current_user=user,
        systems=_system_cards(),
        hierarchy_data=_hierarchy_data(),
    )


@auth_bp.route("/auth/hierarchy")
@_require_login
def hierarchy_page():
    user = get_user_by_id(session.get("user_id"))
    return render_template(
        "auth/hierarchy_page.html",
        current_user=user,
        hierarchy_data=_hierarchy_data(),
    )


@auth_bp.route("/auth/master/hierarchy")
@_require_login
def hierarchy_page_legacy_alias():
    return redirect("/auth/hierarchy")


@auth_bp.route("/auth/open/<app_key>")
@_require_login
def open_internal_app(app_key: str):
    # Integration switchboard:
    # - Keep per-app access checks and start/bridge logic here.
    # - For each new app key, add a branch that validates access and redirects
    #   to a signed SSO bridge URL (or direct URL if that app does not use bridge auth).
    normalized = (app_key or "").strip().lower()
    if normalized != "maintenance":
        flash("You currently only have access to the Maintenance application.", "warning")
        return redirect(url_for("auth.master_landing"))

    if not _ensure_maintenance_online():
        flash("Maintenance application is currently offline (port 5001). Could not auto-start app.py.", "warning")
        return redirect(url_for("auth.master_landing"))

    user_id = str(session.get("user_id") or "").strip()
    role = str(session.get("role") or "").strip()
    if not user_id or not role:
        flash("Session is missing required access information. Please log in again.", "warning")
        return redirect(url_for("auth.login"))
    return redirect(_maintenance_bridge_url(user_id, role))
