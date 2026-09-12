from fastapi.testclient import TestClient

from app.main import create_app
from app.security.principal import Principal, Role
from app.settings.production import AuthMode, Settings


class StubAuthProvider:
    def authenticate(self, token: str) -> Principal:
        principals = {
            "viewer": Principal(user_id="viewer", workspace_id="workspace-a", roles={Role.VIEWER}),
            "analyst": Principal(user_id="analyst", workspace_id="workspace-a", roles={Role.ANALYST}),
            "admin": Principal(user_id="admin", workspace_id="workspace-a", roles={Role.ADMIN}),
        }
        if token not in principals:
            raise ValueError("invalid token")
        return principals[token]


def _client() -> TestClient:
    settings = Settings(
        auth_mode=AuthMode.JWT,
        auth_issuer="https://issuer.example",
        auth_audience="sales-api",
        auth_jwks_url="https://issuer.example/.well-known/jwks.json",
    )
    app = create_app(settings)
    app.state.auth_provider = StubAuthProvider()
    return TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_jwt_boundary_rejects_missing_and_invalid_tokens() -> None:
    client = _client()

    assert client.get("/api/tasks/unknown").status_code == 401
    assert client.get("/api/tasks/unknown", headers=_auth("invalid")).status_code == 401


def test_viewer_is_read_only_and_analyst_cannot_administer_documents() -> None:
    client = _client()

    assert client.get("/api/tasks/unknown", headers=_auth("viewer")).status_code == 404
    assert client.post("/api/exports", headers=_auth("viewer"), json={}).status_code == 403
    assert client.post("/api/documents", headers=_auth("analyst")).status_code == 403


def test_analyst_write_and_admin_document_boundaries_allow_routing() -> None:
    client = _client()

    # 422 proves authorization passed and request validation, rather than RBAC, rejected the payload.
    assert client.post("/api/exports", headers=_auth("analyst"), json={}).status_code == 422
    assert client.post("/api/documents", headers=_auth("admin")).status_code == 422
