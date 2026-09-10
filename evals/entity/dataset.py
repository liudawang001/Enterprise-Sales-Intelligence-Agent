from app.entities.enums import EntityRelationType
from app.research.models import RawEnterpriseCandidate


def _candidate(index: int, side: str, *, name: str, code: str):
    return RawEnterpriseCandidate(
        candidate_id=f"00000000-0000-4000-8000-{index:011d}{1 if side == 'l' else 2}",
        research_run_id="00000000-0000-4000-8000-000000000000",
        source_provider=f"fixture-{side}",
        source_name=name,
        normalized_name=name,
        unified_social_credit_code=code,
    )


def build_entity_pair_dataset() -> list[tuple[RawEnterpriseCandidate, RawEnterpriseCandidate, EntityRelationType]]:
    cases = []
    for index in range(27):
        code = f"91310000SAME{index:06d}"
        cases.append(
            (
                _candidate(index, "l", name=f"上海样本{index}科技有限公司", code=code),
                _candidate(index, "r", name=f"样本{index}科技股份有限公司", code=code),
                EntityRelationType.SAME_ENTITY,
            )
        )
    for index in range(27, 54):
        cases.append(
            (
                _candidate(index, "l", name=f"同名样本{index}有限公司", code=f"91310000LEFT{index:06d}"),
                _candidate(index, "r", name=f"同名样本{index}有限公司", code=f"91310000RGHT{index:06d}"),
                EntityRelationType.DIFFERENT,
            )
        )
    return cases
