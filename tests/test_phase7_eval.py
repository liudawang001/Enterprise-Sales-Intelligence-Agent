from evals.delivery.run_delivery_eval import run_evaluation


def test_phase7_delivery_evaluation_gates():
    report = run_evaluation()
    assert report.snapshot_case_count >= 20
    assert report.export_field_case_count >= 20
    assert report.evidence_case_count >= 20
    assert report.historical_case_count >= 10
    assert report.security_case_count >= 10
    assert report.snapshot_version_accuracy == 1
    assert report.ui_excel_critical_field_consistency == 1
    assert report.export_field_accuracy == 1
    assert report.export_field_allowlist_enforcement == 1
    assert report.evidence_traceability == 1
    assert report.export_idempotency == 1
    assert report.workbook_parse_success == 1
    assert report.unsafe_hyperlink_rejection == 1
    assert report.formula_injection_protection == 1
    assert report.filename_traversal_protection == 1
    assert report.historical_version_accuracy == 1

