from app.evidence.enums import EnterpriseVerificationStatus, FieldVerificationStatus
from app.evidence.models import ResolvedField


def evidence_coverage(fields: dict[str, ResolvedField], required_fields: list[str]) -> float:
    if not required_fields:
        return 1.0
    covered = sum(
        1
        for name in set(required_fields)
        if name in fields and fields[name].status != FieldVerificationStatus.MISSING
    )
    return round(covered / len(set(required_fields)), 4)


def enterprise_status(fields: dict[str, ResolvedField]) -> EnterpriseVerificationStatus:
    statuses = {item.status for item in fields.values()}
    if FieldVerificationStatus.CONFLICTING in statuses:
        return EnterpriseVerificationStatus.CONFLICTING
    if statuses and statuses <= {FieldVerificationStatus.VERIFIED}:
        return EnterpriseVerificationStatus.VERIFIED
    if statuses & {FieldVerificationStatus.VERIFIED, FieldVerificationStatus.PARTIAL}:
        return EnterpriseVerificationStatus.PARTIAL
    return EnterpriseVerificationStatus.UNVERIFIED
