# v1.0.0 Release Notes

## Status: NOT RELEASED — NO-GO

The v1.0 acceptance audit produced real evaluation, E2E, security, recovery and performance artifacts. It did not produce a release tag or GitHub release.

### Accepted improvements in the RC

- Production fake-provider guard and release-branch CI validation.
- Deterministic Evaluation, golden API workflow and mutation scope coverage.
- Region/business mutation classification, enterprise-id exports and enrichment handling.
- Redis bounded failure waits, workspace intelligence scoping and security regression coverage.
- Recovery/performance acceptance artifacts and runbooks.

### Blocking findings

- FA-001: the main production graph still uses in-memory business repositories; full artifact recovery fails.
- Restart/resume completes runtime checkpoint progression but not the full business flow; graceful shutdown exceeds the acceptance budget.
- Production compose image/provider smoke was not executed in this environment.

No version bump, tag, GitHub push or release was performed.

