# Enterprise Sales Intelligence Agent v1.0 Final Acceptance Report

**Audit date:** 2026-09-13 (Asia/Shanghai)  
**Branch:** `release/v1.0.0`  
**FA-001 remediation baseline:** `226dae5` (`fix(persistence): persist production business state`)
**Decision:** **NO-GO**

## Executive decision

The repository was audited in the order required by the acceptance task book. Deterministic Phase 1–8 tests, Evaluation, golden API workflows, security checks, migration, restart, and full business backup/restore now pass. FA-001 has been remediated and re-tested:

- **FA-001 RESOLVED:** production now injects PostgreSQL-backed repositories for the complete business artifact graph. Fresh-application persistence and clarification restart/resume tests passed.
- A real Uvicorn process completed a three-lead request and then handled SIGTERM without SIGKILL, logging complete application shutdown under the 30-second budget.
- Custom-format dump/restore preserved all required business rows; a fresh restored application read historical task/lead/evidence/score/export data, downloaded the XLSX, and resumed a task that was interrupted in the backup.
- Production compose image build/provider smoke and real external-provider quality were not executed in this environment. The browser replay was only partial because the agent-browser account hit its usage limit.

Because the task book requires all 18 Mandatory Release Gates to be PASS, this audit cannot authorize a tag, GitHub release, or production rollout.

## Repository baseline and Phase 1–8 audit

The baseline audit is recorded in [PHASE_IMPLEMENTATION_AUDIT.md](PHASE_IMPLEMENTATION_AUDIT.md). Its FA-001 findings were reproduced before any remediation. `application_lifespan` now builds the runtime only after replacing the complete dependency graph with durable repositories. The detailed repository matrix, test scenarios, database counts, and recovery evidence are in [FA-001_REMEDIATION_REPORT.md](FA-001_REMEDIATION_REPORT.md).

`.env` files were not added and no existing pushed history was rewritten. The final documentation/artifact batch was committed on the release branch and the final working tree was verified clean.

## Acceptance test summary

| Category | Real command/scenario | Result |
|---|---|---|
| Unit / regression | `pytest -q` | **169 passed, 17 skipped, 1 deselected**, 25 warnings |
| Integration | `pytest -q -m integration` with PostgreSQL, restored DB, and Redis | **18 passed** |
| Recovery markers | `pytest -q -m recovery` with source/restored DB URLs | **4 passed** |
| Fault tests | `pytest -q -m fault` | **5 passed** |
| Frontend | `npm test -- --run` | **7 passed** |
| Frontend build | `npm run build` | **PASS** |
| API/E2E selection | Golden selection | **32 passed** |
| Evaluation | RAG/rules/research/entity/evidence/scoring/mutation/delivery | **PASS** on deterministic fixtures |
| FA-001 persistence/recovery | Cross-instance graph, restart, SIGTERM, dump/restore, restored APIs | **PASS** |
| Security | JWT/RBAC/isolation/SSRF/injection/redaction | **28 passed** |
| External providers | Real provider smoke | **NOT_RUN** |
| Production compose | Rendered config | **PASS**; image build/smoke **NOT_RUN** |

Evidence files: [fa001-remediation-summary.json](../artifacts/acceptance/fa001-remediation-summary.json), [evaluation-summary.json](../artifacts/acceptance/evaluation-summary.json), [e2e-summary.json](../artifacts/acceptance/e2e-summary.json), [recovery-summary.json](../artifacts/acceptance/recovery-summary.json), [security-summary.json](../artifacts/acceptance/security-summary.json), [performance-summary.json](../artifacts/acceptance/performance-summary.json).

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

The original golden deterministic flow produced task `1d78914d-648b-41a5-8d39-327b4c948cec`, version 2, delivery snapshot `d331bb4b-5cbf-4f7c-8635-d0e7b6eb8534`, export `eea0490b-fbcc-4f4e-b4a7-b5b6cf67a7bd`, trace `a82292a4-9e00-4111-9a92-00b97e624541`, three leads and an exact 3×5 API/Excel field comparison. Clarification restart/resume is now also PASS against the full PostgreSQL-backed MainGraph.

## Mandatory Release Gates

| # | Gate | Status | Evidence / reason |
|---:|---|---|---|
| 1 | Main Full E2E | **PARTIAL** | API golden flow passed with deterministic providers; real external/production path not run. |
| 2 | Clarification Restart Resume | **PASS** | Application A interrupted; fresh application B resumed the same task and completed the full business flow. |
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
| 14 | Clean DB Migration | **PASS** | Isolated empty database migrated through the complete chain to `0009_fa001_durable_business_state`. |
| 15 | Production Compose Smoke | **NOT_RUN** | Config rendering passed; Docker API/image build and provider smoke unavailable. |
| 16 | Backup / Restore | **PASS** | Required source/restore row counts matched; restored APIs, XLSX download, and interrupted-task resume passed. |
| 17 | Secret Scan | **PASS** | Local Gitleaks: 57 commits, no leaks; pip/npm audits clean. |
| 18 | Final Working Tree Clean | **PASS** | Verified after the final acceptance documentation commit. |

**Mandatory result: 15 PASS, 0 FAIL, 2 PARTIAL, 1 NOT_RUN; overall requirement is not met.** Every mandatory gate must be PASS before release.

## Recovery and security

Provider 429 retry, timeout/circuit breaker, Langfuse fail-open, Redis degradation and bounded Redis waits passed. PostgreSQL custom dump/restore now preserves the complete required artifact set, and restart/resume plus graceful SIGTERM passed. Security regression, workspace isolation, SSRF, prompt-injection-as-data, Excel injection, redaction, Gitleaks, `pip-audit` and `npm audit --omit=dev` passed. No live external IdP/JWKS smoke was available.

## Performance baseline

The local in-process baseline passed with zero measured errors: RAG p95 5.95 ms, task read p95 1.136 ms, lead list p95 1.18 ms, concurrent chat p95 16.869 ms, Excel 100-row p95 229.52 ms, Excel 1000-row p95 2035.466 ms, and 1000-row delivery read p95 277.832 ms. These numbers use in-memory repositories and deterministic fake providers and are not production capacity/SLO evidence.

## UI / browser status

The workspace initial page loaded with zero console errors and screenshot [initial.png](../artifacts/acceptance/ui/screenshots/initial.png) was captured. The request was submitted, but the follow-up browser operation hit the agent-browser usage limit. See [ui-summary.json](../artifacts/acceptance/ui-summary.json); no browser result was inferred.

## Release and external-operation status

- GitHub push: **EXECUTED**. FA-001 core commit `226dae5` was pushed to `origin/release/v1.0.0`; no force push was used.
- GitHub tag/release: **NOT_EXECUTED** because the decision is NO-GO and no release authority was available.
- Real external provider smoke: **NOT_RUN**; credentials were not supplied.
- Production Docker image build/smoke: **NOT_RUN**; Docker API access was denied in this session.

## Required remediation before re-audit

1. Run production-like compose image/provider smoke with authorized real, non-placeholder credentials.
2. Re-run the browser full flow and complete the UI/Excel Mandatory Gate.
3. Re-run all 18 Mandatory Gates, then only if every gate is PASS prepare `v1.0.0`.

Until then, release remains blocked.
