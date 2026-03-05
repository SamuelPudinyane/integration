# Auth Portal Hierarchical Structure

## 1) System Hierarchy (Top-Down)

- **Level 0: Platform Boundary**
  - `auth_portal` (authentication + orchestration gateway)
  - `joburg_water_flask_app` (maintenance application)

- **Level 1: Auth Portal Runtime (`master_app.py`)**
  - Flask app bootstrap
    - Secret and config loading
    - Static/template wiring
    - Blueprint registration: `auth_bp`
  - Process orchestration
    - `_is_port_open(port)`
    - `_start_process(key, command, port)`
    - `PROCESS_REGISTRY`
  - Public gateway routes
    - `/` -> redirects to login
    - `/report-incident` -> proxies to maintenance app
    - `/orchestrator/run-all-apps` -> ensures maintenance app is running
    - `/orchestrator/status` -> health/port status

- **Level 2: Authentication and Session Control (`auth_routes.py`)**
  - Auth service helpers
    - `_maintenance_base_url()`
    - `_is_maintenance_online()`
    - `_ensure_maintenance_online()`
    - `_bridge_signature(user_id, role)`
    - `_maintenance_bridge_url(user_id, role)`
  - Session guard
    - `_require_login` decorator
  - Portal UX entry points
    - `/auth/login` (GET/POST)
    - `/auth/logout`
    - `/auth/master` (landing page)
    - `/auth/open/<app_key>` (open internal app)

- **Level 3: Identity and Data Access (`auth_backend.py`)**
  - Environment + DB initialization
    - `load_dotenv(...)`
    - `get_database_url()`
    - `engine`
  - User domain operations
    - `read_users()`
    - `get_user_by_id(...)`
    - `authenticate_user(username, password)`
  - Source table
    - `public.it_digital_user_account`

- **Level 4: Shared Security/Role Logic (`shared_auth.py`)**
  - Role constants
    - `ROLE_ADMIN = "Maintenance Manager"`
    - `DEFAULT_ADMIN_USERNAME`
  - Canonical role normalization
    - `LEGACY_ROLE_ALIASES`
    - `canonical_role_name(raw_role)`
  - Bridge signing
    - `AUTH_BRIDGE_KEY`
    - `bridge_signature(user_id, role, bridge_key)`

- **Level 5: Downstream App Handoff (Maintenance App)**
  - Auth portal sends signed redirect to:
    - `http://127.0.0.1:5001/auth/bridge-login?user_id=...&role=...&sig=...`
  - Maintenance app validates signature and establishes its own session.

---

## 2) Process Hierarchy (Request Lifecycle)

### A. Login and Session Establishment
1. User requests `/auth/login`.
2. `authenticate_user(...)` validates user from DB.
3. Portal session created (`session["user_id"]`, `session["role"]`).
4. User redirected to `/auth/master`.

### B. Internal App Open (Maintenance)
1. User clicks maintenance app card -> `/auth/open/maintenance`.
2. `_require_login` enforces session presence.
3. `_ensure_maintenance_online()` verifies port `5001` and auto-starts app if needed.
4. `_maintenance_bridge_url(...)` generates signed handoff URL.
5. Browser redirected to maintenance bridge-login endpoint.

### C. Orchestrator Operations
1. `/orchestrator/run-all-apps` calls `_start_process(...)`.
2. Checks if maintenance app is already running on configured port.
3. Starts process if offline; stores process handle in `PROCESS_REGISTRY`.
4. Returns JSON status and URLs.

### D. Community Incident Proxy
1. `/report-incident` on master app.
2. Immediate redirect to maintenance app `/report-incident`.

---

## 3) Relationship Structure

## 3.1 Module Relationships
- `master_app.py` -> registers `auth_bp` from `auth_routes.py`.
- `auth_routes.py` -> calls `auth_backend.py` for identity operations.
- `auth_routes.py` -> calls `shared_auth.py` for signature generation.
- `auth_backend.py` -> calls `shared_auth.py` for role canonicalization.
- `auth_routes.py` -> depends on `master_app.py` config values (`MAINTENANCE_*`, `WORKSPACE_ROOT`).

## 3.2 Data Relationships
- `auth_backend.read_users()` -> `public.it_digital_user_account`.
- `auth_backend.authenticate_user()` -> in-memory lookup over fetched users.
- `shared_auth.canonical_role_name()` -> normalizes legacy role variants before role usage.

## 3.3 Session Relationships
- Portal session keys:
  - `user_id`
  - `role`
- `_require_login` gates access to protected auth routes.
- Portal session is independent from maintenance app session (bridged by signed redirect).

## 3.4 Security Relationships
- Signature input = `user_id:role:AUTH_BRIDGE_KEY`.
- Signature algorithm = SHA-256.
- Auth portal creates signature; maintenance app validates signature.
- Prevents unauthorized direct role/user spoofing in bridge query params.

---

## 4) Hierarchical Diagram (Mermaid)

```mermaid
flowchart TD
  U[User Browser] --> L[/auth/login]
  L --> AR[auth_routes.login]
  AR --> AB[auth_backend.authenticate_user]
  AB --> DB[(public.it_digital_user_account)]
  AR --> S1[Portal Session: user_id, role]
  S1 --> ML[/auth/master]

  ML --> OM[/auth/open/maintenance]
  OM --> EL[_ensure_maintenance_online]
  EL --> ORCH[_is_maintenance_online / subprocess start]
  ORCH --> MA[Maintenance App :5001]

  OM --> SIG[shared_auth.bridge_signature]
  SIG --> BR[/auth/bridge-login?user_id&role&sig]
  BR --> MA

  MAPP[master_app.py] --> BP[register auth_bp]
  MAPP --> OR[/orchestrator/run-all-apps]
  OR --> SP[_start_process]
  SP --> MA

  RP[/report-incident proxy] --> MA
```

---

## 5) Quick Ownership Map

- **Gateway & orchestration owner**: `master_app.py`
- **Auth/session owner**: `auth_routes.py`
- **Identity data owner**: `auth_backend.py`
- **Security normalization/signature owner**: `shared_auth.py`
- **Operational domain owner**: maintenance app (`fake data/joburg_water_flask_app/app.py`)

---

## 6) Practical Reading Order

1. `shared_auth.py` (role + signature core)
2. `auth_backend.py` (DB user model and authentication)
3. `auth_routes.py` (auth flow + bridge)
4. `master_app.py` (runtime bootstrap + orchestration)
