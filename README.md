# Auth Portal Integration Guide (master_app + auth_routes + auth_backend)

This guide covers only the `auth_portal` integration layer and explains how to connect additional internal apps (not just maintenance) to the master login portal.

For a full hierarchy/process map, see [HIERARCHICAL_STRUCTURE.md](HIERARCHICAL_STRUCTURE.md).
For governance and release controls, see [INTEGRATION_POLICY.md](INTEGRATION_POLICY.md) and [ROLLOUT_PLAN.md](ROLLOUT_PLAN.md).

---

## 1) What this layer does

- `master_app.py`
  - Hosts the master login portal (default port `5000`)
  - Registers `auth_bp` from `auth_routes.py`
  - Stores per-app base URLs and startup scripts in `app.config`
- `auth_routes.py`
  - Handles login/logout/master landing (`/auth/login`, `/auth/logout`, `/auth/master`)
  - Opens internal apps via `/auth/open/<app_key>`
  - Generates secure bridge login URL with signature
- `auth_backend.py`
  - Reads users from DB (`public.it_digital_user_account`)
  - Authenticates username/password and returns role/user_id
- `shared_auth.py`
  - Shared constants and helpers used by all auth files
  - Canonical role mapping and bridge signature helper

---

## 2) Prerequisites (do these before any run)

1. **Python installed** (3.11+ recommended).
2. **Database reachable** (PostgreSQL).
3. **User table exists**: `public.it_digital_user_account`.
4. **Environment variables available** in `fake data/.env`:
   - `DB_HOST`
   - `DB_PORT`
   - `DB_NAME`
   - `DB_USER`
   - `DB_PASSWORD`
5. **Install dependencies** in your environment:
   - `flask`
   - `sqlalchemy`
   - `psycopg2-binary`
   - `python-dotenv`
6. **Set auth secrets** (recommended):
   - `AUTH_PORTAL_SECRET_KEY`
   - `AUTH_BRIDGE_KEY`

---

## 3) Mandatory port rules (do not skip)

Each app must have a unique port.

- Master auth portal: `MASTER_PORT` (default `5000`)
- Internal App A (maintenance): `MAINTENANCE_PORT` (default `5001`)
- Internal App B (example finance): use another free port (e.g. `5002`)
- Internal App C (example registration): use another free port (e.g. `5003`)

Never run two apps on the same port.

---

## 4) Current single-app flow (maintenance)

1. Open `master_app.py`:
   - `MASTER_PORT` defines master app port
   - `MAINTENANCE_PORT` defines internal maintenance app port
   - `MAINTENANCE_SCRIPT` points to maintenance app entry file
2. `master_app.py` sets:
   - `MAINTENANCE_APP_BASE_URL`
   - `MAINTENANCE_APP_PORT`
   - `MAINTENANCE_SCRIPT_PATH`
3. `auth_routes.py`:
   - `/auth/login` authenticates via `auth_backend.authenticate_user()`
   - `/auth/open/maintenance` ensures app is running and redirects with signed bridge URL
4. Internal app validates bridge signature at `/auth/bridge-login` and creates session.

---

## 5) Step-by-step: integrate another internal app

Use this exact checklist for each new app.

### Step 1: Reserve a unique port

Choose a free port not already used.

Example:
- `FINANCE_PORT=5002`

### Step 2: Add app script path in `master_app.py`

Add a new path constant like:
- `FINANCE_SCRIPT = WORKSPACE_ROOT / "path" / "to" / "finance_app.py"`

### Step 3: Add config keys in `master_app.py`

Set app config entries for the new app:
- `FINANCE_APP_BASE_URL`
- `FINANCE_APP_PORT`
- `FINANCE_SCRIPT_PATH`

### Step 4: Add startup status support in `master_app.py`

In `run_all_apps()` and/or orchestrator endpoints:
- call `_start_process(...)` for the new app
- include URL + port in JSON response

### Step 5: Extend cards in `auth_routes.py`

In `_system_cards()`:
- add an entry for your new app (`key`, `name`, `description`, `status`, `theme`, `has_access`)

### Step 6: Extend open route logic in `auth_routes.py`

In `open_internal_app(app_key)`:
- accept new `app_key`
- for each key, use corresponding config:
  - base URL
  - port
  - script path
- ensure app is running before redirecting

### Step 7: Keep bridge signing consistent

Use `shared_auth.bridge_signature(...)` in both sides.

- Sender (`auth_routes.py`) signs with:
  - `user_id`, `role`, `AUTH_BRIDGE_KEY`
- Receiver (target app) validates same formula and same key

If keys differ, bridge login fails.

### Step 8: Implement bridge-login endpoint in target app

In each integrated app, implement route equivalent to:
- `/auth/bridge-login?user_id=...&role=...&sig=...`

Validation steps:
1. Check all query params exist.
2. Recompute expected signature.
3. Compare expected vs provided signature.
4. Load user from DB.
5. Verify account active.
6. Set session (`user_id`, `role`).
7. Redirect to app landing page.

### Step 9: Add route fallback/report URL if needed

If portal references app report/landing URLs, ensure target app has those routes.

### Step 10: Role access and menu visibility

Make sure target app enforces role checks after bridge login.

Do not rely only on portal card visibility.

---

## 6) `auth_backend.py` requirements before connecting apps

Before any app can use shared auth login:

1. DB credentials must be correct in `.env`.
2. `public.it_digital_user_account` must include usable records:
   - `user_id`
   - `username`
   - `role_name`
   - `is_active`
3. Role names should map through `shared_auth.canonical_role_name(...)`.
4. At least one active manager/admin user should exist.

---

## 7) Run order (safe startup sequence)

1. Activate Python environment.
2. Ensure env vars are loaded (`fake data/.env`).
3. Start master app:
   - `python auth_portal/master_app.py`
4. Open master login URL:
   - `http://127.0.0.1:<MASTER_PORT>/auth/login`
5. Log in.
6. Open internal app from `/auth/master` card.
7. Confirm redirect to target app via bridge login.

---

## 8) Quick verification checklist

After integrating a new app, verify all:

- [ ] Master app starts on its own unique port.
- [ ] New app starts on a different unique port.
- [ ] `/auth/open/<new_key>` redirects successfully.
- [ ] Target app accepts bridge login and sets session.
- [ ] Unauthorized users cannot access protected pages in target app.
- [ ] Role shown after login is correct.
- [ ] No port collision errors in terminal.

---

## 9) Common failure points

- Same port used by two apps.
- `AUTH_BRIDGE_KEY` mismatch between portal and target app.
- Missing DB env vars in `.env`.
- No active user record in `it_digital_user_account`.
- New app key added to UI card but not handled in open route.
- Target app missing `/auth/bridge-login` route.

---

## 10) Minimal integration template (copy pattern)

For each new internal app:

1. Add `<APP>_PORT` and `<APP>_SCRIPT` in `master_app.py`.
2. Add `<APP>_APP_BASE_URL`, `<APP>_APP_PORT`, `<APP>_APP_SCRIPT_PATH` config.
3. Add `_start_process(...)` call in orchestrator route.
4. Add card entry in `_system_cards()`.
5. Add app-key handling in `open_internal_app(...)`.
6. Ensure target app has bridge-login verification.
7. Confirm role-based authorization inside target app.

That is the complete required sequence; do not skip any step.
