# FA-001 Production Persistence Remediation Report

**Execution date:** 2026-09-13 (Asia/Shanghai)
**Branch:** `release/v1.0.0`
**Core implementation commit:** `226dae5` (`fix(persistence): persist production business state`)
**FA-001 status:** **RESOLVED**
**Overall v1.0 release status:** **NO-GO** (non-FA-001 mandatory gates remain incomplete)

## Production persistence audit

The pre-change production lifespan replaced the checkpointer, lease coordinator, task mirror,
and event repository, but retained the dependency graph created by `build_dependencies()`.
That graph was process-local. The audit was completed before implementation.

| Domain | Repository contract / prior production implementation | Persistent before | Existing tables | Production implementation after remediation | Restart risk after |
|---|---|---:|---|---|---:|
| Knowledge | `InMemoryKnowledgeRepository` | No | `knowledge_documents`, `knowledge_chunks` | `PostgresKnowledgeRepository` | Removed |
| Task / Version | `MockTaskRepository` plus an API-end task mirror | Partial | `lead_tasks`, `lead_task_versions` | `PostgresTaskRepository` | Removed |
| Rule / Criteria | `InMemoryRuleRepository` | No | `business_rules`, `marketing_rules`, `lead_criteria_snapshots` | `PostgresRuleRepository` | Removed |
| Research / Candidate / Source | `InMemoryResearchRepository`; async adapter was not wired and was incomplete for graph reads | No | Phase 4 research tables | `PostgresResearchRepository` | Removed |
| Entity / Relation / Location | `InMemoryEnterpriseRepository`; async adapter was not wired | No | Phase 5 entity tables | `PostgresEnterpriseRepository` | Removed |
| Evidence / Resolved field / Profile | `InMemoryEvidenceRepository`; async adapter was not wired | No | Phase 5 verification tables | `PostgresEvidenceRepository` | Removed |
| Score / Lead set | `InMemoryLeadScoreRepository`; async adapter was not wired | No | Phase 5 scoring tables | `PostgresLeadScoreRepository` | Removed |
| Mutation / Re-execution | `InMemoryMutationRepository` | No | Phase 6 mutation tables | `PostgresMutationRepository` | Removed |
| Execution snapshot | `InMemoryExecutionSnapshotRepository` | No | `task_execution_snapshots` | `PostgresExecutionSnapshotRepository` | Removed |
| Delivery snapshot | `InMemoryDeliverySnapshotRepository` | No | `delivery_snapshots` | `PostgresDeliverySnapshotRepository` | Removed |
| Export metadata/events | `InMemoryExportRepository`; async adapter did not restore events | No | `exports` | `PostgresExportRepository` | Removed |

The production graph no longer instantiates the unused legacy `MockBusinessService` and
`MockScoringService`; their optional compatibility fields are populated only in the in-memory
development/test graph. Rules use `BusinessRuleService`; scoring uses `LeadScoringService` and the
durable repositories listed above.

## Implementation and migration

- `application_lifespan` now verifies both async and sync PostgreSQL connections, constructs the
  complete PostgreSQL business dependency graph, then creates `GraphRuntime` from those durable
  dependencies. Connection failure aborts startup; there is no memory fallback.
- Development/test still use in-memory dependencies when `graph_checkpointer=memory`; development
  can opt into the PostgreSQL graph; production settings require PostgreSQL.
- Synchronous adapters match the existing synchronous graph/service contract and use bounded,
  short SQLAlchemy transactions. A fresh adapter hydrates read caches from PostgreSQL; those
  caches are not the durable source of truth.
- Resolved fields use their database uniqueness key as an idempotent upsert.
- Local export storage rediscovers a restored file from its durable export directory. S3 storage
  rediscovers a single object using the deterministic export prefix.
- Alembic `0009_fa001_durable_business_state` adds resumable JSON payloads for research-run events,
  delivery bundles, and export events. The existing Phase 2–7 tables are reused.
- A brand-new isolated database successfully ran the full `0001` → `0009` migration chain.

## Persistence and recovery tests

The main persistence test creates a complete task in application A, freezes a delivery snapshot,
creates an XLSX export, closes A, builds application B with a new dependency graph/cache, then
reads Task, Criteria, Candidate, SourceRecord, Entity, Evidence, ResolvedField, VerifiedProfile,
LeadScore, ExecutionSnapshot, DeliverySnapshot, Export metadata, and the export file.

The restart test stops application A at a real LangGraph clarification interrupt, starts a fresh
application B, resumes the same thread and task, and completes research, verification, and scoring.

Observed results:

- FA-001 application persistence/restart tests: **3 passed** (including production DB fail-fast).
- Restored-database application tests: **2 passed**.
- Full Python regression: **169 passed, 17 skipped, 1 deselected**.
- Integration marker suite with PostgreSQL and Redis configured: **18 passed, 169 deselected**.
- Recovery marker suite: **4 passed, 183 deselected**.
- Delivery/export focused regression: **13 passed**.
- Real Uvicorn process received SIGTERM after a completed three-lead request and logged
  `Application shutdown complete` / `Finished server process`; no SIGKILL was required and the
  observed shutdown wait was under one second (30-second budget).

## Backup / restore evidence

`pg_dump --format=custom` was executed against the source database. `pg_restore --exit-on-error`
restored it into a newly created isolated PostgreSQL database. A second untouched restore was used
for exact count comparison because the first restored database was deliberately mutated by the
resume test.

| Artifact table | Source | Untouched restore |
|---|---:|---:|
| `lead_tasks` | 14 | 14 |
| `lead_task_versions` | 24 | 24 |
| `enterprise_candidates` | 45 | 45 |
| `research_source_records` | 162 | 162 |
| `enterprise_evidence` | 592 | 592 |
| `resolved_fields` | 273 | 273 |
| `verified_enterprise_profiles` | 15 | 15 |
| `lead_scores` | 15 | 15 |
| `delivery_snapshots` | 3 | 3 |
| `exports` | 3 | 3 |
| `checkpoints` | 770 | 770 |

The untouched restore reported Alembic head `0009_fa001_durable_business_state`. With the restored
export directory mounted, a new application instance returned HTTP 200 for historical task, lead,
evidence, score, export metadata, and XLSX download. A `WAITING_USER` task contained in the dump
also resumed and completed against the restored database.

## Git and remaining release blockers

- Core commit `226dae5` was pushed to `origin/release/v1.0.0` without force.
- The recovery/report follow-up commit and push are recorded in the final handoff after execution.
- FA-001 is resolved. This does not authorize `v1.0.0`: real external-provider E2E remains
  `NOT_RUN`, browser UI replay remains partial, and production-compose provider smoke remains
  `NOT_RUN`. The aggregate release decision therefore remains **NO-GO**.
