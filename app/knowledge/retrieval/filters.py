from datetime import date

from app.knowledge.enums import DocumentAuthority, DocumentStatus
from app.knowledge.models import KnowledgeFilter, KnowledgeQuery


REGION_HIERARCHY = {
    "NATIONAL": ["NATIONAL"],
    "SHANGHAI": ["NATIONAL", "SHANGHAI"],
    "SONGJIANG": ["NATIONAL", "SHANGHAI", "SONGJIANG"],
    "上海": ["NATIONAL", "SHANGHAI"],
    "上海松江": ["NATIONAL", "SHANGHAI", "SONGJIANG"],
    "松江": ["NATIONAL", "SHANGHAI", "SONGJIANG"],
}


class MetadataFilterBuilder:
    def build(self, query: KnowledgeQuery) -> KnowledgeFilter:
        regions = REGION_HIERARCHY.get((query.region or "NATIONAL").upper(), [query.region] if query.region else [])
        return KnowledgeFilter(
            businesses=[query.business] if query.business else [],
            regions=[region for region in regions if region],
            document_types=query.document_types,
            statuses=[DocumentStatus.READY],
            effective_at=query.as_of_date or date.today() if query.current_only else query.as_of_date,
        )
