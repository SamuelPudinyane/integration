# Integration Policy

This policy defines how new internal applications are integrated into the auth portal.

## 1. Policy Scope

This policy applies to:
- Application registration in the auth portal launcher
- Role-based access from the master landing page
- Bridge-login handoff requirements
- App startup orchestration and health visibility

## 2. Single Source of Truth

All integrated app metadata must be declared in [integration_policy.py](integration_policy.py) under `BASE_INTEGRATED_APPS`.

Each app definition must include:
- `key`
- `name`
- `description`
- `enabled`
- `status`
- `rollout_wave`
- `auto_start`
- `requires_bridge`
- `access_roles`
- Config keys for `base_url`, `port`, and `script_path`

No app should be hardcoded directly in route logic without first being registered in policy.

## 3. Access Policy

- Access is controlled by `access_roles` and evaluated through `user_has_app_access(...)`.
- `"*"` means all authenticated users.
- `enabled = false` always overrides role access and keeps the app unavailable.

## 4. Bridge Policy

For apps with `requires_bridge = true`:
- The auth portal must generate a signed bridge payload using `shared_auth.bridge_signature(...)`.
- The target app must validate signature and user role before session creation.

## 5. Rollout Policy

- `rollout_wave` indicates release phase and controls sequencing.
- `status` must match rollout phase state (`Planned`, `Pilot`, `Live`).
- `auto_start` should only be enabled when runtime paths/ports are validated.

## 6. Runtime Policy Checks

- Orchestrator startup and status routes use policy metadata from `integration_policy.py`.
- Master landing cards are generated from policy metadata.
- Open-app routing must check both registration and role access before redirect.

## 7. Required Review Before Enabling an App

Before changing `enabled` to `true`:
1. Port assignment confirmed and unique.
2. Script path exists and starts locally.
3. Bridge endpoint exists in target app.
4. Role map reviewed with business owner.
5. Smoke test passed from login to app landing.

## 8. Change Management

For every policy change:
- Update app entry in [integration_policy.py](integration_policy.py)
- Update rollout progress in [ROLLOUT_PLAN.md](ROLLOUT_PLAN.md)
- Capture test evidence in pull request notes
