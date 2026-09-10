from __future__ import annotations

import json
from collections import defaultdict

from app.evidence.confidence import calculate_evidence_confidence
from app.evidence.enums import FieldVerificationStatus
from app.evidence.models import Evidence, ResolvedField
from app.evidence.policies import policy_for


class ConflictAwareFieldResolver:
    def resolve(self, enterprise_id: str, field_name: str, values: list[Evidence]) -> ResolvedField:
        if not values:
            return ResolvedField(enterprise_id=enterprise_id, field_name=field_name, status=FieldVerificationStatus.MISSING, confidence=0)
        groups: dict[str, list[Evidence]] = defaultdict(list)
        for item in values:
            key = json.dumps(
                item.normalized_value,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            groups[key].append(item)
        policy = policy_for(field_name)
        priority = {source.value: index for index, source in enumerate(policy.source_priorities)}
        scored_groups = []
        for group in groups.values():
            scored = []
            for item in group:
                confidence, stale = calculate_evidence_confidence(item, policy, agreement_count=len(group))
                item.confidence, item.stale = confidence, stale
                scored.append(confidence)
            best_priority = min(priority.get(item.source_type.value, len(priority)) for item in group)
            scored_groups.append((sum(scored) / len(scored), len(group), -best_priority, group))
        scored_groups.sort(key=lambda item: item[:3], reverse=True)
        average, agreement_count, _, primary_group = scored_groups[0]
        conflict = len(scored_groups) > 1
        if conflict:
            status = FieldVerificationStatus.CONFLICTING
        elif agreement_count >= policy.min_sources_for_verified and average >= policy.min_confidence:
            status = FieldVerificationStatus.VERIFIED
        elif average >= policy.min_confidence:
            status = FieldVerificationStatus.PARTIAL
        else:
            status = FieldVerificationStatus.UNVERIFIED
        conflicting = [item.evidence_id for _, _, _, group in scored_groups[1:] for item in group]
        return ResolvedField(
            enterprise_id=enterprise_id,
            field_name=field_name,
            primary_value=primary_group[0].value,
            status=status,
            confidence=round(average * (0.75 if conflict else 1), 4),
            supporting_evidence_ids=[item.evidence_id for item in primary_group],
            conflicting_evidence_ids=conflicting,
            alternatives=[group[0].value for _, _, _, group in scored_groups[1:]],
            selection_reason=f"source_priority+freshness+agreement:{primary_group[0].source_type.value}",
        )
