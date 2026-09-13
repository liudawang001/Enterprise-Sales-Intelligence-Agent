# v1.0 Architecture Acceptance Baseline

Status: Release Candidate audit; **NO-GO**.

```text
FastAPI -> MainGraph/LangGraph -> Phase 1-7 business services
                         |                |
                         |                +-- in-memory repositories (current blocker)
                         +-- PostgreSQL: tasks, versions, events, leases, checkpoints
                         +-- Redis: cache, rate limit, stream (lossy by design)
```

Phase 8 correctly wires the production runtime and checkpoint path, but the main graph still constructs in-memory repositories for research, evidence, scoring, delivery, knowledge and the task mirror used by the business flow. Therefore a process restart can restore a checkpoint while losing the business artifacts needed to finish the run. This is recorded as FA-001 and prevents release.

Production configuration rejects fake research providers and requires authentication/provider settings. The deterministic fake providers remain available only for local synthetic evaluation and demo workflows.

The durable boundary currently verified by audit is: Alembic schema, task/version rows, execution runs, events, leases and LangGraph checkpoints. The unverified/non-durable boundary is the complete business artifact graph (candidate sets, evidence, scores and exports).

