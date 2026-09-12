from __future__ import annotations

import threading
from collections import defaultdict
from time import monotonic

METRIC_NAMES = {
    "http_requests_total",
    "http_request_duration_seconds",
    "http_errors_total",
    "active_sse_connections",
    "agent_runs_total",
    "agent_run_duration_seconds",
    "agent_interrupts_total",
    "agent_resume_total",
    "agent_resume_failures_total",
    "checkpoint_errors_total",
    "provider_calls_total",
    "provider_errors_total",
    "provider_rate_limited_total",
    "provider_cache_hits_total",
    "provider_request_duration_seconds",
    "research_candidates_discovered",
    "research_candidates_verified",
    "mutation_scope_total",
    "partial_reexecution_total",
    "full_replan_total",
    "stale_promotion_rejected_total",
    "export_jobs_total",
    "export_failures_total",
    "export_duration_seconds",
    "export_rows_total",
}
FORBIDDEN_LABELS = {"task_id", "enterprise_id", "user_id", "trace_id", "thread_id", "run_id"}


class MetricsRegistry:
    def __init__(self) -> None:
        self._values: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._lock = threading.Lock()

    def add(self, name: str, value: float = 1, **labels: str) -> None:
        if name not in METRIC_NAMES:
            raise ValueError("UNKNOWN_METRIC")
        if FORBIDDEN_LABELS.intersection(labels):
            raise ValueError("HIGH_CARDINALITY_LABEL")
        key = (name, tuple(sorted((item, str(value)) for item, value in labels.items())))
        with self._lock:
            self._values[key] += value

    def render(self) -> str:
        lines = []
        with self._lock:
            values = dict(self._values)
        for (name, labels), value in sorted(values.items()):
            suffix = "{" + ",".join(f'{key}="{item}"' for key, item in labels) + "}" if labels else ""
            lines.append(f"{name}{suffix} {value}")
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()


class Timer:
    def __init__(self) -> None:
        self.started = monotonic()

    @property
    def seconds(self) -> float:
        return monotonic() - self.started
