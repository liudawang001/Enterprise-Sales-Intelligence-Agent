import pytest
from pydantic import ValidationError

from app.observability.redaction import SecretRedactor
from app.settings.production import Settings


def test_production_rejects_unsafe_auth_and_memory_checkpoint() -> None:
    with pytest.raises(ValidationError, match="AUTH_MODE=disabled"):
        Settings(app_env="production")
    with pytest.raises(ValidationError, match="GRAPH_CHECKPOINTER=postgres"):
        Settings(
            app_env="production",
            auth_mode="jwt",
            auth_issuer="issuer",
            auth_audience="audience",
            auth_jwks_url="https://id.example/jwks",
            database_url="postgresql+asyncpg://user:strong@db.example/app",
        )


def test_secret_redactor_masks_headers_key_values_and_dsn_password() -> None:
    value = SecretRedactor().redact(
        {
            "Authorization": "Bearer abc.def",
            "message": "api_key=secret DATABASE_URL=postgres://user:password@db/app",
            "nested": {"token": "raw"},
        }
    )
    rendered = str(value)
    assert "abc.def" not in rendered
    assert "secret" not in rendered
    assert "password@" not in rendered
    assert "raw" not in rendered
    assert rendered.count("[REDACTED]") >= 4
