# Recovery Runbook (v1.0 RC)

## Health triage

- `/health/live` proves the process is serving.
- `/health/ready` reports dependency readiness.
- `/health/dependencies` identifies PostgreSQL/Redis degradation and includes a trace id.
- Redis loss is expected to degrade cache/rate/stream features; PostgreSQL remains the source for durable runtime records.

## Database backup

Use a custom-format `pg_dump`, record the source commit and Alembic head, restore into an isolated database with `pg_restore`, then run `alembic current` and compare task/version/checkpoint counts before traffic is restored.

## Current acceptance result

FA-001 recovery acceptance passed on 2026-09-13. The restored database reached Alembic head
`0009_fa001_durable_business_state`; source and untouched-restore counts matched for tasks,
versions, candidates, source records, evidence, resolved fields, profiles, scores, delivery
snapshots, exports, and checkpoints. A fresh application read all key artifacts and downloaded a
restored XLSX. A clarification-interrupted task resumed after both application restart and database
restore. Uvicorn completed SIGTERM shutdown without SIGKILL and within the 30-second budget.

Database backup is not sufficient for local export storage: back up and restore the configured
export volume at the same consistency point. S3 deployments must retain the `exports/{export_id}/`
objects together with the database metadata.
