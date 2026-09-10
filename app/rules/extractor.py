from __future__ import annotations

import re

from app.rules.models import ExtractedBusinessRule, OfficialRuleExtractionInput, OfficialRuleExtractionResult, RuleModality, RuleOperator


OFFICIAL_RULE_PROMPT = """Extract business rules only from the supplied evidence chunks.
Do not use external knowledge. Do not turn marketing advice or product features into official eligibility rules.
Every extracted rule must cite one or more supplied evidence_chunk_ids. Put non-executable facts in ignored_facts.
Return the OfficialRuleExtractionResult schema."""


class OfficialRuleExtractor:
    def __init__(self, llm=None) -> None:
        self.llm = llm

    def extract(self, payload: OfficialRuleExtractionInput) -> OfficialRuleExtractionResult:
        if self.llm is not None:
            structured = self.llm.with_structured_output(OfficialRuleExtractionResult)
            return structured.invoke({"instruction": OFFICIAL_RULE_PROMPT, "input": payload.model_dump(mode="json")})
        rules: list[ExtractedBusinessRule] = []
        ignored: list[str] = []
        for chunk in payload.evidence_chunks:
            match = re.search(r"成员(?:数|数量).{0,16}(?:至少|不少于|不低于)\s*(\d+)", chunk.content)
            if match:
                rules.append(ExtractedBusinessRule(field="member_count", operator=RuleOperator.GTE, value=int(match.group(1)), value_type="INTEGER", modality=RuleModality.REQUIRED, confidence=1.0, rationale="业务资料明确要求成员数量下限", evidence_chunk_ids=[chunk.chunk_id]))
            if re.search(r"多个办公地点|多办公点", chunk.content):
                rules.append(ExtractedBusinessRule(field="office_count", operator=RuleOperator.GTE, value=2, value_type="INTEGER", modality=RuleModality.RECOMMENDED, confidence=0.85, rationale="业务资料将多办公点描述为推荐特征", evidence_chunk_ids=[chunk.chunk_id]))
            if "短号互拨" in chunk.content:
                ignored.append("支持内部短号互拨属于业务特征，不能直接转换为企业筛选条件")
        return OfficialRuleExtractionResult(rules=rules, ignored_facts=ignored)

