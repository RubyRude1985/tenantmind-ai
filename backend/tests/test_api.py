import os

os.environ["DATABASE_URL"] = "sqlite:///./test_tenantmind_v2.db"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def register(email: str, workspace: str) -> dict[str, str]:
    response = client.post("/api/auth/register", json={
        "name": "Portfolio User", "workspace_name": workspace,
        "email": email, "password": "secure-password",
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "2.0.0"


def test_auth_and_grounded_answer() -> None:
    headers = register("alpha@example.com", "Alpha")
    document = client.post("/api/documents/text", headers=headers, json={
        "title": "Refund policy", "content": "Refund requests are reviewed within five business days and returned to the original card.",
    })
    assert document.status_code == 201
    response = client.post("/api/chat", headers=headers, json={"question": "How are refund requests reviewed?"})
    assert response.status_code == 200
    assert response.json()["citations"][0]["title"] == "Refund policy"
    assert response.json()["citations"][0]["similarity"] > 0


def test_tenant_isolation() -> None:
    alpha = register("alpha@example.com", "Alpha")
    beta = register("beta@example.com", "Beta")
    client.post("/api/documents/text", headers=alpha, json={"title": "Private note", "content": "Alpha confidential operating procedure."})
    assert client.get("/api/documents", headers=beta).json() == []
    response = client.post("/api/chat", headers=beta, json={"question": "What is Alpha procedure?"})
    assert response.json()["citations"] == []


def test_text_file_upload_and_dashboard() -> None:
    headers = register("files@example.com", "Files")
    response = client.post("/api/documents/upload", headers=headers, files={
        "file": ("handbook.txt", b"Remote work requests require manager approval and a security review.", "text/plain")
    })
    assert response.status_code == 201
    stats = client.get("/api/dashboard", headers=headers).json()
    assert stats["documents"] == 1 and stats["chunks"] == 1


def test_invalid_token_is_rejected() -> None:
    assert client.get("/api/documents", headers={"Authorization": "Bearer invalid"}).status_code == 401
