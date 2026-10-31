from pathlib import Path
import re

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import URL

from app.core.config import Settings
from app.main import create_app


def test_health_and_openapi(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "subcadence-api"}
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "SubCadence API"
    assert set(schema["paths"]) == {
        "/api/v1/health", "/api/v1/auth/signup", "/api/v1/auth/login", "/api/v1/auth/me",
        "/api/v1/auth/logout", "/api/v1/auth/password-reset/request",
        "/api/v1/auth/password-reset/confirm", "/api/v1/users/staff", "/api/v1/dev/email-outbox",
    }


def test_health_executes_database_query(client: TestClient) -> None:
    statements: list[str] = []
    engine = client.app.state.session_factory.kw["bind"]

    def record_query(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_query)
    try:
        assert client.get("/api/v1/health").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", record_query)
    assert "SELECT 1" in statements


def test_documentation_assets_are_local(client: TestClient) -> None:
    html = client.get("/docs").text
    assets = re.findall(r'(?:src|href)="([^"]+)"', html)
    assert len(assets) == 3
    for asset in assets:
        assert asset.startswith("/docs-assets/")
        response = client.get(asset)
        assert response.status_code == 200
        assert len(response.content) > 100
    assert '"validatorUrl": null' in html


def test_health_database_failure_is_sanitized(tmp_path: Path) -> None:
    # SQLite cannot open a directory as a database: exercise a real connection failure.
    url = URL.create("sqlite", database=str(tmp_path)).render_as_string()
    with TestClient(create_app(Settings(_env_file=None, database_url=url))) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert str(tmp_path) not in response.text


def test_cors_allows_only_configured_origin(client: TestClient) -> None:
    headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    headers["Origin"] = "https://untrusted.example"
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_requests_receive_separate_closed_sessions(client: TestClient) -> None:
    factory = client.app.state.session_factory
    sessions = []
    # Instrument the real factory, retaining real database connections and cleanup.
    def tracked_factory():
        session = factory()
        sessions.append(session)
        return session

    client.app.state.session_factory = tracked_factory
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]
    assert all(not session.in_transaction() for session in sessions)
