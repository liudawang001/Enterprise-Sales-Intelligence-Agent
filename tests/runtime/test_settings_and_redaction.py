import pytest
from pydantic import ValidationError

from app.main import create_app
from app.observability.redaction import SecretRedactor
from app.providers.adapters import CommercialEnterpriseProvider
from app.providers.factory import ProviderFactory
from app.settings.production import Settings


def production_settings(**overrides) -> dict:
    values = {
        "app_env": "production",
        "auth_mode": "jwt",
        "auth_issuer": "issuer",
        "auth_audience": "audience",
        "auth_jwks_url": "https://id.example/jwks",
        "graph_checkpointer": "postgres",
        "database_url": "postgresql+asyncpg://user:strong@db.example/app",
        "enterprise_provider": "commercial",
        "enterprise_api_base_url": "https://enterprise.example",
        "enterprise_api_key": "enterprise-test-key",
        "map_provider": "amap",
        "amap_api_key": "amap-test-key",
        "web_search_provider": "tavily",
        "tavily_api_key": "tavily-test-key",
        "web_fetch_provider": "firecrawl",
        "firecrawl_api_key": "firecrawl-test-key",
    }
    values.update(overrides)
    return values


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


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"enterprise_provider": "fake"}, "real provider configuration"),
        ({"enterprise_api_key": ""}, "ENTERPRISE_API_KEY"),
        ({"allowed_origins": "*"}, "wildcard CORS"),
        ({"rag_debug": True}, "debug output"),
    ],
)
def test_production_rejects_fake_or_unsafe_runtime_configuration(overrides, error) -> None:
    with pytest.raises(ValidationError, match=error):
        Settings(**production_settings(**overrides))


def test_provider_factory_never_silently_falls_back_for_incomplete_named_provider() -> None:
    settings = Settings(enterprise_provider="commercial", enterprise_api_base_url="", enterprise_api_key="")
    with pytest.raises(ValueError, match="ENTERPRISE_PROVIDER_CONFIGURATION_INVALID"):
        ProviderFactory.build(settings)


def test_create_app_uses_the_explicit_settings_for_dependency_construction() -> None:
    settings = Settings(
        enterprise_provider="commercial",
        enterprise_api_base_url="https://enterprise.example",
        enterprise_api_key="test-key",
    )
    application = create_app(settings)
    provider = application.state.dependencies.research_service.providers.enterprise
    assert isinstance(provider, CommercialEnterpriseProvider)
