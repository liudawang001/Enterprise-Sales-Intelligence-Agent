from __future__ import annotations

import json
import os
import platform
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from math import ceil
from statistics import median
from time import perf_counter

from fastapi.testclient import TestClient

from app.exports.registry import ExportFieldRegistry
from app.exports.workbook import build_workbook
from app.knowledge.enums import DocumentAuthority, DocumentStatus
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument
from app.main import create_app
from scripts.benchmark_phase7_delivery import expand_bundle


def summarize(samples: list[float], *, errors: int, duration: float, concurrency: int) -> dict:
    ordered = sorted(samples)
    return {
        "request_count": len(samples),
        "concurrency": concurrency,
        "duration_seconds": round(duration, 3),
        "p50_ms": round(median(ordered), 3),
        "p95_ms": round(ordered[max(0, ceil(len(ordered) * 0.95) - 1)], 3),
        "error_rate": round(errors / len(samples), 6),
        "throughput_rps": round(len(samples) / duration, 3),
    }


def measure(call, count: int, *, concurrency: int = 1) -> dict:
    def one(index: int) -> tuple[float, bool]:
        started = perf_counter()
        response = call(index)
        return (perf_counter() - started) * 1000, response.status_code >= 400

    started = perf_counter()
    if concurrency == 1:
        results = [one(index) for index in range(count)]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            results = list(executor.map(one, range(count)))
    duration = perf_counter() - started
    return summarize(
        [latency for latency, _error in results],
        errors=sum(error for _latency, error in results),
        duration=duration,
        concurrency=concurrency,
    )


def seed_rag(app) -> None:
    repository = app.state.knowledge_repository
    document = KnowledgeDocument(
        title="Acceptance RAG Document",
        original_filename="acceptance.pdf",
        file_hash="a" * 64,
        business="集团V网",
        region="NATIONAL",
        authority=DocumentAuthority.DEMO,
        status=DocumentStatus.READY,
        file_path="acceptance.pdf",
        effective_from=date(2026, 1, 1),
    )
    repository.create_document(document)
    content = "集团V网主要面向具有企业内部通信需求的集团客户。"
    repository.replace_chunks(
        document.id,
        [
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=0,
                content=content,
                lexical_content="集团 V 网 主要 面向 企业 内部 通信 需求 集团 客户",
                embedding=app.state.knowledge_service.embedding.embed_query(content),
                page_start=1,
                page_end=1,
                content_hash="b" * 64,
                metadata={"document_title": document.title, "authority": "DEMO"},
            )
        ],
    )


def measure_workbook(bundle, rows: int, repeats: int) -> dict:
    expanded = expand_bundle(bundle, rows)
    fields = ExportFieldRegistry().validate(
        ["rank", "enterprise_id", "enterprise_name", "industry", "lead_score", "verification_status"]
    )
    samples: list[float] = []
    size_bytes = 0
    started = perf_counter()
    for index in range(repeats):
        sample_started = perf_counter()
        content = build_workbook(
            expanded,
            fields,
            target_count=rows,
            export_id=f"acceptance-{rows}-{index}",
            exported_at=datetime.now(UTC),
            include_task_summary=True,
            include_score_breakdown=True,
            include_evidence_summary=True,
            include_conflicts=True,
        )
        samples.append((perf_counter() - sample_started) * 1000)
        size_bytes = len(content)
    result = summarize(samples, errors=0, duration=perf_counter() - started, concurrency=1)
    result.update({"rows": rows, "size_bytes": size_bytes})
    return result


def run() -> dict:
    app = create_app()
    seed_rag(app)
    with TestClient(app) as client:
        task_started = perf_counter()
        completed = client.post(
            "/api/chat",
            json={"session_id": "performance-seed", "message": "帮我找上海松江3家集团V网企业"},
        )
        task_latency_ms = (perf_counter() - task_started) * 1000
        completed.raise_for_status()
        task_id = completed.json()["task_id"]
        task = client.get(f"/api/tasks/{task_id}").json()["task"]
        version = task["version"]

        rag = measure(
            lambda index: client.post(
                "/api/chat",
                json={"session_id": f"performance-rag-{index}", "message": "集团V网主要面向什么客户？"},
            ),
            20,
        )
        task_read = measure(lambda _index: client.get(f"/api/tasks/{task_id}"), 100)
        lead_list = measure(
            lambda index: client.get(
                f"/api/tasks/{task_id}/versions/{version}/leads",
                params={"page": index % 2 + 1, "page_size": 2, "sort_by": "rank"},
            ),
            100,
        )
        concurrent_chat = measure(
            lambda index: client.post(
                "/api/chat",
                json={
                    "session_id": f"performance-concurrent-{index}",
                    "message": "集团V网主要面向什么客户？",
                },
            ),
            20,
            concurrency=4,
        )
        bundle = app.state.dependencies.delivery_query_service.freeze(task_id, version)
        workbook_100 = measure_workbook(bundle, 100, 5)
        workbook_1000 = measure_workbook(bundle, 1000, 3)

    return {
        "measured_at": datetime.now(UTC).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_cpu_count": os.cpu_count(),
            "api_mode": "FastAPI TestClient / in-process",
            "database": "in-memory repositories",
            "providers": "deterministic fake",
            "rag_documents": 1,
            "rag_chunks": 1,
            "lead_result_rows": 3,
        },
        "parameters": {
            "rag_requests": 20,
            "task_read_requests": 100,
            "lead_list_requests": 100,
            "concurrent_chat_requests": 20,
            "concurrent_chat_workers": 4,
        },
        "full_sales_flow_seed": {
            "request_count": 1,
            "latency_ms": round(task_latency_ms, 3),
            "error_rate": 0.0,
        },
        "rag_query": rag,
        "task_read_api": task_read,
        "lead_list_pagination": lead_list,
        "concurrent_chat": concurrent_chat,
        "excel_export_100": workbook_100,
        "excel_export_1000": workbook_1000,
        "limitations": [
            "This is a repeatable local baseline, not a capacity claim.",
            "The benchmark does not represent production PostgreSQL, Redis, network providers, "
            "JWT verification, or multiple API processes.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
