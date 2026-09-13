# Deployment Runbook (v1.0 RC)

This runbook is for a release candidate. It does not authorize production release while `FINAL_ACCEPTANCE_REPORT.md` is NO-GO.

## Required sequence

1. Provide non-placeholder `DATABASE_URL`, Redis URL, OIDC/JWT issuer, audience and JWKS settings, plus enabled provider credentials.
2. Run `alembic upgrade head` against an empty or reviewed database.
3. Run `python -m scripts.init_checkpointer`.
4. Verify `/health/live`, `/health/ready` and `/health/dependencies`.
5. Start API and frontend from the pinned commit; keep fake providers disabled in production.
6. Run the full smoke and recovery checklist before any traffic is admitted.

## Acceptance evidence

Migration to `0008_phase8_production_runtime` and idempotent seed were executed against acceptance PostgreSQL. Compose interpolation/config rendering passed. Production image build and provider-backed smoke were **NOT_RUN**: Docker API access was unavailable in this session and real external credentials were not supplied.

## Rollback

Stop new traffic, preserve logs/checkpoints, restore the last approved database backup, and redeploy the last approved commit. No v1.0.0 tag exists because this audit is NO-GO.

