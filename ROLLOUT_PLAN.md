# Integration Rollout Plan

This is the suggested rollout sequence for enabling additional apps through the auth portal.

## Wave 1 (Current)

- App: Maintenance Management System
- Policy state: `enabled=true`, `status=Live`, `auto_start=true`
- Objective: Stable production handoff and role-safe access

## Wave 2 (Suggested)

- App: Finance Management System
- Initial policy state: `enabled=false`, `status=Planned`, `auto_start=false`

### Wave 2 checklist

1. Confirm finance app bridge endpoint implementation.
2. Assign dedicated port and environment variables.
3. Add runtime config keys in [master_app.py](master_app.py).
4. Run pilot with `status=Pilot`, limited to manager/inventory roles.
5. Validate bridge signature and role-restricted page access.
6. Enable `auto_start` only after startup reliability is proven.
7. Promote to `enabled=true`, `status=Live`.

## Wave 3 (Suggested)

- App: Registration & Records System
- Initial policy state: `enabled=false`, `status=Planned`, `auto_start=false`

### Wave 3 checklist

1. Implement bridge-login route in registration app.
2. Configure role model and verify least-privilege scope.
3. Validate startup command and health checks.
4. Pilot with selected users and monitor login/redirect failures.
5. Promote to live after incident-free pilot window.

## Cross-wave rollout controls

- Keep only one new app in pilot at a time.
- Keep rollback path available by switching `enabled=false` in policy.
- Track rollout evidence per app:
  - Startup success
  - Auth handoff success
  - Authorization enforcement
  - Error and latency metrics

## Rollback procedure

If issues are found during pilot/live:
1. Set app `enabled=false` in [integration_policy.py](integration_policy.py).
2. Set app `status=Planned`.
3. Disable `auto_start`.
4. Restart master portal process.
5. Re-run smoke tests for unaffected apps.

## Operational owner checklist

Before each promotion step:
- Security owner signs off bridge validation.
- Application owner signs off role matrix.
- Platform owner confirms startup and status telemetry.
