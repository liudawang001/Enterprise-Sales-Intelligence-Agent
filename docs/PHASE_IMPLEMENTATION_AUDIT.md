# Phase 1-8 Implementation Audit

Audit date: 2026-09-12 (Asia/Shanghai)

Scope: source tree at `f70c9eb097c7bf9d4504ddd9c672b5d3bbe0b863`, before acceptance fixes.

Statuses in this document describe implementation evidence only. Test, evaluation, E2E,
recovery, security, and release-gate statuses are recorded after their respective real runs
in `FINAL_ACCEPTANCE_REPORT.md`.

## Repository baseline

- Remote: `https://github.com/liudawang001/Enterprise-Sales-Intelligence-Agent.git`
- Remote default ref: `origin/feat/phase1-langgraph-runtime`
- Default integration branch present: `origin/main`
- `origin/main` and the remote default ref both resolved to `f70c9eb` after `git fetch --prune origin`.
- Phase 1-8 history is reachable from `origin/main`; `origin/feat/phase7-delivery-workspace` is an ancestor.
- Acceptance branch: `release/v1.0.0`, created from `origin/main`.
- Existing tags: none.
- Initial tracked inventory: 406 files: 241 backend, 69 tests, 19 eval files,
  39 frontend files, 11 migrations, 9 scripts, 2 workflows, and 4 Phase 7 screenshots.
- Initial test collection: 164 selected tests and 1 deselected external test (`pytest --collect-only -q`).
- Alembic has one linear head: `0008_phase8_production_runtime`.
- The worktree was clean after switching to the acceptance branch. Existing generated
  exports/uploads, frontend dependencies/build output, and egg-info are ignored and were
  preserved.
- Initial push of the release branch was rejected by the execution safety policy and is
  therefore `NOT_EXECUTED`; no workaround was attempted.

## Repository capability inventory

| Area | Evidence | Audit status |
|---|---|---|
| Backend | FastAPI, LangGraph, RAG, rules, research, entity/evidence/scoring, mutation, delivery, runtime packages under `app/` | PASS |
| Frontend | React/Vite workspace, task/version, lead/evidence/score/export components under `frontend/src/` | PASS |
| Tests | 69 tracked test files; 164 selected tests collected | PASS |
| Evaluations | RAG, rule, research, entity, evidence/scoring, mutation, delivery runners under `evals/` | PASS |
| Migrations | Linear `0001` through `0008` Alembic chain | PASS |
| Scripts | seed, checkpointer init, backup, restore, smoke, benchmark scripts | PASS |
| Deployment | API/frontend Dockerfiles and production-like Compose | PASS |
| CI | backend, integration/recovery/fault, eval, frontend, audit, secret scan, Docker build jobs | PARTIAL |
| Release docs | README exists; dedicated v1.0 audit/report/runbooks/release notes absent at baseline | PARTIAL |

CI is `PARTIAL` because the push trigger covers only `main` and `feat/**`, not the
prescribed `release/**` acceptance branch. This is finding FA-003.

## Phase implementation matrix

| Phase | Core capability | Primary implementation evidence | Implementation audit |
|---|---|---|---|
| 1 | Stateful runtime | `app/agent/graph.py`, requirement subgraph, `interrupt()`, `Command(resume=...)`, distinct session/task IDs | PASS |
| 2 | Grounded RAG | ingestion/parser/chunking, dense+sparse+RRF+rerank, evidence gate, citations, abstention | PASS |
| 3 | Rule and criteria | four source types, official-evidence validation, conflict interrupt, versioned stable criteria hash | PASS |
| 4 | Enterprise research | real adapters, capability-aware planning, budget, retry, idempotency, SSRF/contact controls, source lineage | PARTIAL |
| 5 | Entity/evidence/scoring | hard-negative matching, relations, field evidence conflict preservation, verified profile, deterministic score/explain | PASS |
| 6 | Partial re-execution | versioned mutations, seven scopes, reuse/invalidation planning, stale task promotion guard | PASS |
| 7 | UI and Excel | React workspace, frozen snapshots, historical export, workbook generation and injection guards | PASS |
| 8 | Production engineering | persistent checkpointer, PostgreSQL lease/fence, Redis, tracing, JWT/workspace guard, containers, backup/restore | PARTIAL |

Phase 4 is partial because real adapter classes exist, but production configuration silently
falls back to fake providers. Phase 8 is partial because durable infrastructure exists but the
main application dependency graph remains backed by mock/in-memory business repositories.

## Stub, mock, and production-path findings

### FA-001 — BLOCKER — Production main graph uses mock/in-memory business state

Evidence:

- `app/main.py:create_app()` calls `build_dependencies()`.
- `app/agent/dependencies.py:build_dependencies()` creates `MockTaskRepository`,
  `MockBusinessService`, `MockScoringService`, `InMemoryResearchRepository` (through
  `ResearchService`), and in-memory entity/evidence/score/mutation/delivery/export repositories.
- The production lifespan replaces only the execution coordinator, task mirror, event
  repository, cache/rate limiter, and graph checkpointer. It does not replace the graph's
  business repositories.

Reproduction with valid-looking production settings printed:

```text
dependencies= MockTaskRepository MockBusinessService MockScoringService InMemoryExecutionSnapshotRepository
checkpointer= postgres
```

Impact: restart recovery cannot prove durable Phase 2-7 business artifacts; production path
still uses mocks. This meets the acceptance task's BLOCKER definition.

### FA-002 — BLOCKER — Production provider configuration silently enables fakes

Evidence:

- `ProviderFactory.build()` falls back to a fake adapter whenever a provider name, base URL,
  or credential is absent/unsupported.
- Production validation does not reject fake research providers or missing production provider
  credentials.
- Compose does not pass enterprise/map/search/fetch provider settings to the API service.

Reproduction with otherwise valid production settings printed:

```text
providers= FakeEnterpriseProvider FakeMapProvider FakeWebSearchProvider FakeWebFetchProvider
```

Impact: a production-like deployment can start and return fixed synthetic candidates. This is
an explicit release BLOCKER.

### FA-003 — MAJOR — CI does not run on the release branch

Evidence: `.github/workflows/ci.yml` push branches are `main` and `feat/**` only.

Impact: milestone pushes to `release/v1.0.0` would not receive push-triggered mandatory CI.

### FA-004 — MAJOR — Required v1.0 documentation is absent from the tracked repository

Evidence: the baseline had zero tracked `docs/**` files. The acceptance report, release notes,
architecture, deployment/recovery runbooks, and demo guide did not exist as tracked artifacts.

Impact: documentation and release artifact gates cannot pass until these are created and audited.

### FA-005 — MAJOR — Package and application versions remain `0.8.0`

Evidence: `pyproject.toml`, `app/main.py`, and `frontend/package.json` advertise `0.8.0`.

Impact: release metadata is not prepared for v1.0.0. Version changes are deferred until GO/RC.

## Configuration audit

Confirmed safeguards:

- Production rejects disabled auth.
- Production requires the PostgreSQL graph checkpointer.
- Production requires JWT issuer, audience, and JWKS URL.
- Production rejects the default PostgreSQL credential substring.
- Default CORS is restricted to local origins, not `*`.
- Secrets are represented by environment variables and selected settings use `SecretStr`.
- Docker runs the API as an unprivileged user.

Open production gaps:

- Production does not reject fake providers, missing LLM/embedding/reranker configuration,
  debug flags, or wildcard CORS.
- Application construction does not consistently use the `Settings` instance passed to
  `create_app()`; `build_dependencies()` reads cached global settings.
- Durable Phase 2-7 repository adapters are present in parts, but are not wired as one durable
  production dependency graph.

## Test and acceptance coverage gaps observed during implementation audit

- The restart test proves a small standalone LangGraph interrupt graph survives a checkpointer
  restart; it does not exercise the production application's complete clarification flow.
- No test executes the full main workflow in a restarted production application with durable
  Phase 2-7 artifacts.
- Workspace tests cover task/export reads and knowledge filtering, but do not yet demonstrate
  all task/thread/enterprise/export read/resume/download attack cases against production storage.
- Fault tests cover Redis fail behavior and Langfuse shutdown failure; API process kill,
  research mid-crash reuse, provider 429/timeout/circuit/fallback, graceful shutdown, and actual
  backup/restore still require real acceptance execution.
- External provider smoke is credential-gated and was not run during this implementation audit.

## Audit decision

Implementation audit: **FAIL** for release readiness.

Release decision at this milestone: **NO-GO** because FA-001 and FA-002 are open BLOCKERs.
No tag or GitHub Release is permitted. The next step is the documented blocker fix loop,
followed by the full regression and all remaining mandatory gates.

## FA-001 re-audit — 2026-09-13

FA-001 is **RESOLVED** by `226dae5`. Production startup now constructs PostgreSQL-backed
repositories for knowledge, tasks/versions, rules/criteria, research/candidates/sources,
entities, evidence/resolved fields/profiles, scoring, mutations, execution snapshots, delivery
snapshots, and exports. A PostgreSQL connection failure aborts startup rather than falling back to
memory. Full-graph cross-instance persistence, clarification restart/resume, SIGTERM shutdown,
custom-format dump/restore, restored API reads/download, and restored unfinished-task resume all
passed. See `FA-001_REMEDIATION_REPORT.md` for commands, counts, and residual non-FA-001 blockers.
