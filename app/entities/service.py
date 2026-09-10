from __future__ import annotations

from datetime import UTC, datetime
from itertools import combinations

from app.entities.blocking import EntityBlocker
from app.entities.enums import EntityRelationType, EntityType, ResolutionStatus
from app.entities.matcher import DeterministicEntityMatcher
from app.entities.models import (
    CanonicalEnterprise,
    EnterpriseCandidateLink,
    EntityResolutionRun,
)
from app.research.models import RawEnterpriseCandidate


class EntityResolutionService:
    def __init__(self, repository, matcher: DeterministicEntityMatcher | None = None) -> None:
        self.repository = repository
        self.blocker = EntityBlocker()
        self.matcher = matcher or DeterministicEntityMatcher()

    def resolve(self, *, task_id: str, candidate_set_id: str) -> EntityResolutionRun:
        candidates = self.repository.research_repository.get_candidates(candidate_set_id)
        run = self.repository.save_resolution_run(EntityResolutionRun(task_id=task_id, researched_candidate_set_id=candidate_set_id, candidate_count=len(candidates)))
        parent = {item.candidate_id: item.candidate_id for item in candidates}

        def find(value: str) -> str:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = parent[value]
            return value

        def union(left: str, right: str) -> None:
            parent[find(right)] = find(left)

        decisions = []
        by_id = {item.candidate_id: item for item in candidates}
        for group in self.blocker.build_groups(candidates):
            for left_id, right_id in combinations(group.candidate_ids, 2):
                decision = self.matcher.match(by_id[left_id], by_id[right_id])
                self.repository.save_resolution_decision(run.resolution_run_id, decision)
                decisions.append(decision)
                if decision.relation == EntityRelationType.SAME_ENTITY:
                    union(left_id, right_id)

        clusters: dict[str, list[RawEnterpriseCandidate]] = {}
        for item in candidates:
            clusters.setdefault(find(item.candidate_id), []).append(item)
        enterprise_by_candidate: dict[str, CanonicalEnterprise] = {}
        for cluster in clusters.values():
            primary = max(cluster, key=lambda item: (bool(item.unified_social_credit_code), len(item.source_name)))
            entity_type = EntityType.BRANCH if any("分公司" in item.source_name for item in cluster) else EntityType.OFFICE if any("办事处" in item.source_name for item in cluster) else EntityType.LEGAL_ENTITY
            enterprise = self.repository.save_enterprise(CanonicalEnterprise(canonical_name=primary.source_name, entity_type=entity_type, unified_social_credit_code=primary.unified_social_credit_code, primary_website=primary.website_candidate or primary.source_url, primary_region=primary.region, resolution_status=ResolutionStatus.RESOLVED, resolution_confidence=min((d.confidence for d in decisions if d.left_candidate_id in {v.candidate_id for v in cluster} and d.relation == EntityRelationType.SAME_ENTITY), default=1), source_candidate_ids=[item.candidate_id for item in cluster]))
            for item in cluster:
                enterprise_by_candidate[item.candidate_id] = enterprise
                self.repository.save_candidate_link(EnterpriseCandidateLink(enterprise_id=enterprise.enterprise_id, candidate_id=item.candidate_id, resolution_run_id=run.resolution_run_id, confidence=enterprise.resolution_confidence))
        self.repository.materialize_relations(decisions, enterprise_by_candidate)
        return self.repository.save_resolution_run(run.model_copy(update={"status": "COMPLETED", "enterprise_count": len(clusters), "finished_at": datetime.now(UTC)}))
