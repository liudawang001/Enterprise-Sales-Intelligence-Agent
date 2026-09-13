# Recovery Runbook (v1.0 RC)

## Health triage

- `/health/live` proves the process is serving.
- `/health/ready` reports dependency readiness.
- `/health/dependencies` identifies PostgreSQL/Redis degradation and includes a trace id.
- Redis loss is expected to degrade cache/rate/stream features; PostgreSQL remains the source for durable runtime records.

## Database backup

Use a custom-format `pg_dump`, record the source commit and Alembic head, restore into an isolated database with `pg_restore`, then run `alembic current` and compare task/version/checkpoint counts before traffic is restored.

## Current acceptance result

Backup/restore mechanics passed: the restored database reached Alembic head and preserved task/version/checkpoint rows. The full business artifact restore gate failed because evidence, scores and exports were not persisted by the main production graph. A restart also resumed the checkpoint but did not complete the business flow within the acceptance timeout; graceful SIGTERM exceeded the 30-second budget and required forced termination. Do not treat this build as production recoverable.

