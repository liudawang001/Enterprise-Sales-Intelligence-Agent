from __future__ import annotations

from collections import defaultdict

from app.entities.models import ResolutionGroup
from app.entities.normalizer import (
    EnterpriseNameNormalizer,
    PhoneNormalizer,
    WebsiteNormalizer,
)
from app.research.models import RawEnterpriseCandidate


class EntityBlocker:
    def __init__(self) -> None:
        self.names = EnterpriseNameNormalizer()
        self.phones = PhoneNormalizer()
        self.websites = WebsiteNormalizer()

    def build_groups(self, candidates: list[RawEnterpriseCandidate]) -> list[ResolutionGroup]:
        blocks: dict[str, set[str]] = defaultdict(set)
        reasons: dict[str, str] = {}
        for item in candidates:
            name = self.names.normalize(item.source_name)
            keys = [(f"name:{name.base_name}", "NORMALIZED_BASE_NAME")]
            domain = self.websites.normalize(item.website_candidate or item.source_url)
            phone = self.phones.normalize(item.public_phone)
            if domain:
                keys.append((f"domain:{domain}", "SAME_DOMAIN"))
            if phone:
                keys.append((f"phone:{phone}", "SAME_PHONE"))
            if item.provider_group_id:
                keys.append((f"provider:{item.provider_group_id}", "PROVIDER_GROUP"))
            if item.region and name.base_name:
                keys.append((f"region:{item.region}:{name.base_name}", "REGION_STRONG_NAME"))
            for key, reason in keys:
                blocks[key].add(item.candidate_id)
                reasons[key] = reason
        covered: set[tuple[str, ...]] = set()
        groups = []
        for key, ids in blocks.items():
            if len(ids) < 2:
                continue
            signature = tuple(sorted(ids))
            if signature in covered:
                continue
            covered.add(signature)
            groups.append(ResolutionGroup(candidate_ids=list(signature), blocking_reason=reasons[key]))
        return groups
