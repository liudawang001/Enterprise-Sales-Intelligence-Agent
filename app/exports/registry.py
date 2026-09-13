from __future__ import annotations

from pydantic import BaseModel


class ExportFieldDefinition(BaseModel):
    field_key: str
    display_name: str
    source_path: str
    data_type: str
    default_visible: bool = True
    exportable: bool = True
    sensitive: bool = False
    formatter: str | None = None


class ExportFieldRegistry:
    def __init__(self) -> None:
        values = [
            ("rank", "排名", "rank", "INTEGER"),
            ("enterprise_id", "企业 ID", "enterprise_id", "TEXT"),
            ("enterprise_name", "企业名称", "enterprise_name", "TEXT"),
            ("parent_enterprise", "上级集团 / 母公司", "parent_enterprise", "TEXT"),
            ("industry", "行业", "industry", "TEXT"),
            ("company_scale", "企业规模", "company_scale", "TEXT"),
            ("region", "目标区域", "region", "TEXT"),
            ("office_count", "办公点数量", "office_count", "INTEGER"),
            ("office_address", "主要办公地址", "office_address", "TEXT"),
            ("public_phone", "公开联系电话", "public_phone", "TEXT"),
            ("website", "官网", "website", "URL"),
            ("recommended_business", "推荐业务", "recommended_business", "TEXT"),
            ("lead_score", "潜客评分", "lead_score", "NUMBER"),
            ("verification_status", "核验状态", "verification_status", "STATUS"),
            ("evidence_confidence", "证据置信度", "evidence_confidence", "PERCENT"),
            ("recommendation_reason", "推荐理由", "recommendation_reason", "TEXT"),
            ("primary_source", "主要来源", "primary_source", "TEXT"),
            ("primary_source_url", "来源链接", "primary_source_url", "URL"),
            ("verified_at", "核验时间", "verified_at", "DATETIME"),
        ]
        self._fields = {
            key: ExportFieldDefinition(
                field_key=key,
                display_name=name,
                source_path=path,
                data_type=data_type,
            )
            for key, name, path, data_type in values
        }
        self._fields["private_contact"] = ExportFieldDefinition(
            field_key="private_contact",
            display_name="私人联系方式",
            source_path="private_contact",
            data_type="TEXT",
            default_visible=False,
            exportable=False,
            sensitive=True,
        )

    def get(self, key: str) -> ExportFieldDefinition | None:
        return self._fields.get(key)

    def public_fields(self) -> list[ExportFieldDefinition]:
        return [
            item
            for item in self._fields.values()
            if item.exportable and not item.sensitive
        ]

    def validate(self, fields: list[str]) -> list[ExportFieldDefinition]:
        if len(fields) != len(set(fields)):
            raise ValueError("DUPLICATE_EXPORT_FIELD")
        result = []
        for key in fields:
            value = self.get(key)
            if not value:
                raise ValueError(f"UNKNOWN_EXPORT_FIELD:{key}")
            if value.sensitive or not value.exportable:
                raise ValueError(f"SENSITIVE_EXPORT_FIELD:{key}")
            result.append(value)
        return result
