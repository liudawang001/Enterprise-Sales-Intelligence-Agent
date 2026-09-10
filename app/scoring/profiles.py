from app.scoring.models import ScoreComponentConfig, ScoringProfile


def _components() -> list[ScoreComponentConfig]:
    return [
        ScoreComponentConfig(component="business_fit", weight=30, required_fields=["company_status"]),
        ScoreComponentConfig(component="office_distribution", weight=20, required_fields=["office_count", "cross_region_presence"], missing_policy="NEUTRAL", config={"target": 3}),
        ScoreComponentConfig(component="company_scale", weight=15, required_fields=["company_scale", "employee_count"], missing_policy="REWEIGHT"),
        ScoreComponentConfig(component="industry_preference", weight=10, required_fields=["industry"], missing_policy="REWEIGHT"),
        ScoreComponentConfig(component="location_fit", weight=10, required_fields=["address"], missing_policy="ZERO"),
        ScoreComponentConfig(component="evidence_confidence", weight=10, required_fields=[], config={}),
        ScoreComponentConfig(component="contact_completeness", weight=5, required_fields=["public_phone", "website", "address"], missing_policy="ZERO"),
    ]


def demo_scoring_profiles() -> list[ScoringProfile]:
    return [
        ScoringProfile(business_code="GROUP_VNET", version=1, components=_components(), min_evidence_coverage=0.45, hard_required_fields=["legal_name"]),
        ScoringProfile(business_code="ENTERPRISE_DEDICATED_LINE", version=1, components=_components(), min_evidence_coverage=0.5, hard_required_fields=["legal_name", "address"]),
    ]
