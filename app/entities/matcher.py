from __future__ import annotations

from difflib import SequenceMatcher

from app.entities.enums import EntityRelationType
from app.entities.models import AmbiguousEntityResolver, ResolutionDecision
from app.entities.normalizer import (
    AddressNormalizer,
    EnterpriseNameNormalizer,
    PhoneNormalizer,
    WebsiteNormalizer,
)
from app.research.models import RawEnterpriseCandidate


class DeterministicEntityMatcher:
    def __init__(self, ambiguous_resolver: AmbiguousEntityResolver | None = None) -> None:
        self.ambiguous_resolver = ambiguous_resolver
        self.names = EnterpriseNameNormalizer()
        self.addresses = AddressNormalizer()
        self.phones = PhoneNormalizer()
        self.websites = WebsiteNormalizer()

    def match(self, left: RawEnterpriseCandidate, right: RawEnterpriseCandidate) -> ResolutionDecision:
        signals: list[str] = []
        positives: list[str] = []
        negatives: list[str] = []
        if left.unified_social_credit_code and right.unified_social_credit_code:
            if left.unified_social_credit_code != right.unified_social_credit_code:
                negatives.append("DIFFERENT_CREDIT_CODE")
                return self._decision(left, right, EntityRelationType.DIFFERENT, 1, signals, positives, negatives)
            positives.append("SAME_CREDIT_CODE")
            return self._decision(left, right, EntityRelationType.SAME_ENTITY, 1, signals, positives, negatives)
        provider_relation = left.provider_relation or right.provider_relation
        relation_map = {
            "BRANCH_OF": EntityRelationType.BRANCH_OF,
            "SUBSIDIARY_OF": EntityRelationType.SUBSIDIARY_OF,
            "OFFICE_OF": EntityRelationType.OFFICE_OF,
            "STORE_OF": EntityRelationType.STORE_OF,
            "DIFFERENT": EntityRelationType.DIFFERENT,
        }
        if provider_relation in relation_map:
            relation = relation_map[provider_relation]
            marker = f"PROVIDER_{provider_relation}"
            (negatives if relation == EntityRelationType.DIFFERENT else positives).append(marker)
            return self._decision(left, right, relation, 1, signals, positives, negatives)

        ln, rn = self.names.normalize(left.source_name), self.names.normalize(right.source_name)
        similarity = SequenceMatcher(None, ln.base_name, rn.base_name).ratio()
        if similarity >= 0.9:
            signals.append("STRONG_NAME_MATCH")
        if ln.base_name == rn.base_name and (ln.branch_marker or rn.branch_marker):
            return self._decision(left, right, EntityRelationType.BRANCH_OF, 0.95, signals + ["BRANCH_MARKER"], positives, negatives)
        if ln.base_name == rn.base_name and (ln.office_marker or rn.office_marker):
            return self._decision(left, right, EntityRelationType.OFFICE_OF, 0.9, signals + ["OFFICE_MARKER"], positives, negatives)
        domain_match = bool(self.websites.normalize(left.website_candidate or left.source_url) and self.websites.normalize(left.website_candidate or left.source_url) == self.websites.normalize(right.website_candidate or right.source_url))
        phone_match = bool(self.phones.normalize(left.public_phone) and self.phones.normalize(left.public_phone) == self.phones.normalize(right.public_phone))
        address_match = bool(self.addresses.normalize(left.address) and self.addresses.normalize(left.address) == self.addresses.normalize(right.address))
        if domain_match:
            signals.append("SAME_DOMAIN")
        if phone_match:
            signals.append("SAME_PHONE")
        if address_match:
            signals.append("SAME_ADDRESS")
        if similarity >= 0.9 and domain_match:
            return self._decision(left, right, EntityRelationType.SAME_ENTITY, 0.95, signals, positives, negatives)
        if similarity >= 0.9 and phone_match and address_match:
            return self._decision(left, right, EntityRelationType.SAME_ENTITY, 0.92, signals, positives, negatives)
        confidence = min(0.84, 0.45 * similarity + 0.2 * domain_match + 0.15 * phone_match + 0.1 * address_match)
        if 0.50 <= confidence < 0.85 and self.ambiguous_resolver:
            result = self.ambiguous_resolver.resolve(left.model_dump(), right.model_dump(), signals)
            if result.relation != EntityRelationType.DIFFERENT or not negatives:
                return self._decision(left, right, result.relation, confidence, signals + ["LLM_AMBIGUOUS"], positives, negatives, True)
        relation = EntityRelationType.POSSIBLY_RELATED if confidence >= 0.50 else EntityRelationType.DIFFERENT
        return self._decision(left, right, relation, confidence, signals, positives, negatives)

    @staticmethod
    def _decision(left, right, relation, confidence, signals, positives, negatives, llm_used=False):
        return ResolutionDecision(left_candidate_id=left.candidate_id, right_candidate_id=right.candidate_id, relation=relation, confidence=confidence, signals=signals, hard_positives=positives, hard_negatives=negatives, llm_used=llm_used)
