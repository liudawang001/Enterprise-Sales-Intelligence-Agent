# Enterprise Sales Intelligence Agent v1.0 Final Acceptance Report

**Audit date:** 2026-09-13 (Asia/Shanghai)  
**Branch:** `release/v1.0.0`  
**Acceptance code baseline:** `ce6bef6` (`test(perf): record v1.0 performance baseline`)  
**Decision:** **NO-GO**

## Executive decision

The repository was audited in the order required by the acceptance task book. Deterministic Phase 1–8 tests, Evaluation, golden API workflows, security checks, migration and backup mechanics passed. The release is nevertheless blocked by a real production-path persistence defect and failed recovery gates:

- **FA-001 (BLOCKER):** the production main graph still uses in-memory Phase 2–7 business repositories. PostgreSQL preserves runtime/task/checkpoint records, but not the complete candidate/evidence/score/export artifact graph.
- A process restart restored and advanced a LangGraph checkpoint, but the resumed 3-lead business flow did not complete within 30 seconds and remained `RUNNING`; graceful SIGTERM exceeded the configured 30-second grace period and required SIGKILL.
- Full business artifact restore failed: source and restored databases both contained zero evidence, score and export rows after completed synthetic golden flows.
- Production compose image build/provider smoke and real external-provider quality were not executed in this environment. The browser replay was only partial because the agent-browser account hit its usage limit.

Because the task book requires all 18 Mandatory Release Gates to be PASS, this audit cannot authorize a tag, GitHub release, or production rollout.

## Repository baseline and Phase 1–8 audit

The baseline audit is recorded in [PHASE_IMPLEMENTATION_AUDIT.md](PHASE_IMPLEMENTATION_AUDIT.md). It found the implemented Phase 1–8 modules and tests, but also verified that `application_lifespan` replaces durable runtime components without replacing the main business repositories. Production configuration now rejects fake providers; that fix does not remove FA-001.

`.env` files were not added and no existing pushed history was rewritten. The final documentation/artifact batch was committed on the release branch and the final working tree was verified clean.

## Acceptance test summary

| Category | Real command/scenario | Result |
|---|---|---|
| Unit / regression | `pytest -q` | **168 passed, 13 skipped, 1 deselected**, 25 warnings |
| Integration | `pytest -q -m integration` | **13 passed** |
| Recovery markers | `pytest -q -m recovery` | **1 passed** |
| Fault tests | `pytest -q -m fault` | **5 passed** |
| Frontend | `npm test -- --run` | **7 passed** |
| Frontend build | `npm run build` | **PASS** |
| API/E2E selection | Golden selection | **32 passed** |
| Evaluation | RAG/rules/research/entity/evidence/scoring/mutation/delivery | **PASS** on deterministic fixtures |
| Recovery | Redis/provider/Langfuse/backup mechanics | **FAIL overall**; see recovery artifact |
| Security | JWT/RBAC/isolation/SSRF/injection/redaction | **28 passed** |
| External providers | Real provider smoke | **NOT_RUN** |
| Production compose | Rendered config | **PASS**; image build/smoke **NOT_RUN** |

Evidence files: [evaluation-summary.json](../artifacts/acceptance/evaluation-summary.json), [e2e-summary.json](../artifacts/acceptance/e2e-summary.json), [recovery-summary.json](../artifacts/acceptance/recovery-summary.json), [security-summary.json](../artifacts/acceptance/security-summary.json), [performance-summary.json](../artifacts/acceptance/performance-summary.json).

## Evaluation summary

All metrics below are actual deterministic synthetic fixture results; they are not claims about external-provider quality.

| Domain | Metric | Result |
|---|---|---:|
| RAG | Recall@5 (dense/sparse/hybrid) | 1.0 / 1.0 / 1.0 |
| RAG | Citation coverage / no-evidence abstention | 1.0 / 1.0 |
| Rule | Exact match / evidence binding / conflict accuracy | 1.0 / 1.0 / 1.0 |
| Entity | Precision / recall / F1 / hard-negative accuracy | 1.0 / 1.0 / 1.0 / 1.0 |
| Evidence | Conflict detection / primary selection / traceability | 1.0 / 1.0 / 1.0 |
| Scoring | Determinism / monotonicity / profile reproducibility | 1.0 / 1.0 / 1.0 |
| Mutation | Scope accuracy / unsafe under-reexecution / reuse / fence / idempotency | 1.0 / 0.0 / 1.0 / 1.0 / 1.0 |
| Delivery | Snapshot, export, evidence, historical and security fixture rates | 1.0 |

## Golden E2E and mutation evidence

The golden deterministic flow produced task `1d78914d-648b-41a5-8d39-327b4c948cec`, version 2, delivery snapshot `d331bb4b-5cbf-4f7c-8635-d0e7b6eb8534`, export `eea0490b-fbcc-4f4e-b4a7-b5b6cf67a7bd`, trace `a82292a4-9e00-4111-9a92-00b97e624541`, three leads and an exact 3×5 UI/API/Excel field comparison. Clarification, conflict handling, historical export and all six mutation scenarios passed in one process. Production restart/resume is explicitly not reported as PASS.

## Mandatory Release Gates

| # | Gate | Status | Evidence / reason |
|---:|---|---|---|
| 1 | Main Full E2E | **PARTIAL** | API golden flow passed with deterministic providers; real external/production path not run. |
| 2 | Clarification Restart Resume | **FAIL** | Checkpoint advanced after restart, but full business flow remained RUNNING and timed out. |
| 3 | Rule Conflict | **PASS** | Conflict E2E and rule evaluation passed. |
| 4 | Evidence Traceability | **PASS** | Evidence evaluation and golden lineage passed; persistence is separately blocked. |
| 5 | Deterministic Scoring | **PASS** | Determinism/profile/hard-missing evaluation passed. |
| 6 | Partial Re-execution | **PASS** | DISPLAY_ONLY, RANK_ONLY, ENRICHMENT, DISCOVERY and FULL_REPLAN cases passed. |
| 7 | Unsafe Under-reexecution = 0 | **PASS** | Fixed fixtures: `0.0`. |
| 8 | Stale Task Promotion Prevention | **PASS** | Version fence evaluation passed. |
| 9 | Stale Worker Fence Rejection | **PASS** | Runtime/fault coverage passed. |
| 10 | Workspace Isolation | **PASS** | 28 security tests passed, including cross-workspace route checks. |
| 11 | UI / Excel Snapshot Consistency | **PARTIAL** | API/Excel comparison passed; browser replay was interrupted by tool quota. |
| 12 | Excel Injection Protection | **PASS** | Formula and unsafe hyperlink checks passed. |
| 13 | SSRF Regression | **PASS** | Private/loopback/link-local rejection tests passed. |
| 14 | Clean DB Migration | **PASS** | Empty acceptance database migrated to `0008_phase8_production_runtime`. |
| 15 | Production Compose Smoke | **NOT_RUN** | Config rendering passed; Docker API/image build and provider smoke unavailable. |
| 16 | Backup / Restore | **FAIL** | Dump/restore mechanics passed, but full business artifact rows were absent after restore (FA-001). |
| 17 | Secret Scan | **PASS** | Local Gitleaks: 57 commits, no leaks; pip/npm audits clean. |
| 18 | Final Working Tree Clean | **PASS** | Verified after the final acceptance documentation commit. |

**Mandatory result: 13 PASS, 2 FAIL, 2 PARTIAL, 1 NOT_RUN; overall requirement is not met.** Any FAIL is NO-GO.

## Recovery and security

Provider 429 retry, timeout/circuit breaker, Langfuse fail-open, Redis degradation and bounded Redis waits passed. PostgreSQL custom dump/restore reached Alembic head and preserved task/version/checkpoint rows. The complete artifact restore and restart completion failures are the release blockers. Security regression, workspace isolation, SSRF, prompt-injection-as-data, Excel injection, redaction, Gitleaks, `pip-audit` and `npm audit --omit=dev` passed. No live external IdP/JWKS smoke was available.

## Performance baseline

The local in-process baseline passed with zero measured errors: RAG p95 5.95 ms, task read p95 1.136 ms, lead list p95 1.18 ms, concurrent chat p95 16.869 ms, Excel 100-row p95 229.52 ms, Excel 1000-row p95 2035.466 ms, and 1000-row delivery read p95 277.832 ms. These numbers use in-memory repositories and deterministic fake providers and are not production capacity/SLO evidence.

## UI / browser status

The workspace initial page loaded with zero console errors and screenshot [initial.png](../artifacts/acceptance/ui/screenshots/initial.png) was captured. The request was submitted, but the follow-up browser operation hit the agent-browser usage limit. See [ui-summary.json](../artifacts/acceptance/ui-summary.json); no browser result was inferred.

## Release and external-operation status

- GitHub push: **EXECUTED**. Branch `release/v1.0.0` was pushed to `origin` after explicit user authorization; no force push was used.
- GitHub tag/release: **NOT_EXECUTED** because the decision is NO-GO and no release authority was available.
- Real external provider smoke: **NOT_RUN**; credentials were not supplied.
- Production Docker image build/smoke: **NOT_RUN**; Docker API access was denied in this session.

## Required remediation before re-audit

1. Replace all production main-graph Phase 2–7 in-memory repositories with durable PostgreSQL-backed repositories and persist evidence, scores, delivery snapshots and exports.
2. Re-run kill/restart, graceful shutdown and full artifact backup/restore tests against the production graph.
3. Run production-like compose image smoke and one authorized provider smoke with real non-placeholder credentials.
4. Re-run the browser full flow and all 18 Mandatory Gates, then only if every gate is PASS prepare `v1.0.0`.

Until then, release remains blocked.
