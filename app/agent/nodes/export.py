from __future__ import annotations

import re

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.exports.models import CreateExportRequest
from app.exports.service import ExportError

FIELD_TERMS = {
    "排名": "rank",
    "企业名称": "enterprise_name",
    "公司名": "enterprise_name",
    "母公司": "parent_enterprise",
    "行业": "industry",
    "规模": "company_scale",
    "区域": "region",
    "办公点": "office_count",
    "地址": "office_address",
    "电话": "public_phone",
    "官网": "website",
    "评分": "lead_score",
    "核验状态": "verification_status",
    "置信度": "evidence_confidence",
    "推荐理由": "recommendation_reason",
    "来源链接": "primary_source_url",
}
DEFAULT_EXPORT_FIELDS = [
    "rank",
    "enterprise_name",
    "lead_score",
    "verification_status",
]


def make_export_node(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        task_id = state.get("target_task_id") or state.get("active_task_id")
        task = deps.task_repository.get_task(task_id)
        if not task:
            return {
                "response_text": "未找到可导出的任务。",
                "errors": [{"code": "TASK_NOT_FOUND", "message": "TASK_NOT_FOUND"}],
            }
        text = state.get("incoming_text") or ""
        version_match = re.search(r"(?:(?:Task\s*)?[vV]|版本\s*)(\d+)", text)
        version = task.version
        if version_match:
            version = int(version_match.group(1))
        count_match = re.search(r"(?:Top\s*)?(\d+)\s*家?", text, re.IGNORECASE)
        target_count = int(count_match.group(1)) if count_match else None
        requested = [field for term, field in FIELD_TERMS.items() if term in text]
        fields = list(dict.fromkeys(requested)) or task.export_fields or DEFAULT_EXPORT_FIELDS
        try:
            job = deps.export_service.create_export(
                CreateExportRequest(
                    task_id=task.task_id,
                    task_version=version,
                    target_count=target_count,
                    fields=fields,
                )
            )
        except ExportError as exc:
            code = str(exc).split(":", 1)[0]
            return {
                "response_text": f"导出未生成：{exc}",
                "export_spec": {
                    "task_id": task.task_id,
                    "task_version": version,
                    "target_count": target_count,
                    "fields": fields,
                },
                "progress": {"event": "EXPORT_FAILED", "error_code": code},
                "errors": [{"code": code, "message": str(exc)}],
            }
        return {
            "response_text": (
                f"Excel 已生成：{job.file_name}，共 {job.row_count} 行，"
                f"绑定 Task v{job.task_version}。"
            ),
            "export_spec": {
                "task_id": job.task_id,
                "task_version": job.task_version,
                "snapshot_id": job.snapshot_id,
                "fields": job.requested_fields,
            },
            "export_id": job.export_id,
            "export_path": job.artifact_path,
            "artifact_ref": job.export_id,
            "progress": {"event": "EXPORT_COMPLETED", "export_id": job.export_id},
        }

    return node
