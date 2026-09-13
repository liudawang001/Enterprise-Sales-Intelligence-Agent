# v1.0.0 Release Notes

## Status: NOT RELEASED — NO-GO

The v1.0 acceptance audit produced real evaluation, E2E, security, recovery and performance artifacts. It did not produce a release tag or GitHub release.

### Accepted improvements in the RC

- Production fake-provider guard and release-branch CI validation.
- Deterministic Evaluation, golden API workflow and mutation scope coverage.
- Region/business mutation classification, enterprise-id exports and enrichment handling.
- Redis bounded failure waits, workspace intelligence scoping and security regression coverage.
- Recovery/performance acceptance artifacts and runbooks.
- FA-001 durable PostgreSQL repositories for the full production business artifact graph.
- Cross-process clarification resume, full-artifact backup/restore, restored export download, and
  graceful SIGTERM recovery validation.

### Blocking findings

- Real external-provider E2E has not been executed with authorized credentials.
- Full browser UI replay remains partial.
- API/frontend image builds passed in CI; production-compose service/provider smoke remains unexecuted.

The release branch was pushed. No version bump, tag, or GitHub release was performed because the
aggregate acceptance decision remains NO-GO.
