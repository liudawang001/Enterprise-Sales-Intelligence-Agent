from app.exports.registry import ExportFieldRegistry
from app.exports.sanitizer import (
    safe_http_url,
    safe_spreadsheet_text,
    sanitize_filename,
)


def test_registry_rejects_unknown_duplicate_and_sensitive_fields():
    registry = ExportFieldRegistry()
    for fields, code in (
        (["unknown"], "UNKNOWN_EXPORT_FIELD"),
        (["rank", "rank"], "DUPLICATE_EXPORT_FIELD"),
        (["private_contact"], "SENSITIVE_EXPORT_FIELD"),
    ):
        try:
            registry.validate(fields)
        except ValueError as exc:
            assert code in str(exc)
        else:
            raise AssertionError("invalid registry field accepted")


def test_formula_url_and_filename_security_guards():
    for value in ('=HYPERLINK("https://evil.example")', "+1+1", "@SUM(A1:A2)", "-cmd"):
        assert safe_spreadsheet_text(value).startswith("'")
    for value in ("javascript:alert(1)", "file:///etc/passwd", "data:text/html,x"):
        assert safe_http_url(value) is None
    assert safe_http_url("https://example.com/path") == "https://example.com/path"
    for value in ("../../lead.xlsx", "/var/tmp/a.xlsx", "..\\..\\lead.xlsx", "bad\x00name.xlsx"):
        result = sanitize_filename(value)
        assert "/" not in result and "\\" not in result and ".." not in result
        assert result.endswith(".xlsx")
        assert len(result) <= 105
