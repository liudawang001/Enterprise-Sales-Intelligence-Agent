from app.agent.enums import IntentType, MutationScope, TaskStage, TaskStatus
from app.domain.task import ConstraintPatch, Lead, LeadTask, TaskPatch


def test_domain_models_and_enums_are_importable() -> None:
    patch = TaskPatch(
        business="集团V网",
        region="上海松江",
        target_count=50,
        constraints=[ConstraintPatch(field="industry", operation="REMOVE")],
    )
    task = LeadTask(
        task_id="task-1",
        session_id="session-1",
        stage=TaskStage.COLLECTING_REQUIREMENTS,
        status=TaskStatus.RUNNING,
    )
    lead = Lead(company_name="示例企业")

    assert patch.constraints[0].operation == "REMOVE"
    assert task.task_id != task.session_id
    assert lead.company_name == "示例企业"
    assert IntentType.LEAD_DISCOVERY == "LEAD_DISCOVERY"
    assert MutationScope.FULL_REPLAN == "FULL_REPLAN"
