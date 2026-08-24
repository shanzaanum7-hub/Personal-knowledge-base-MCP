import json
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import Settings


def make_test_client():
    test_settings = Settings(
        jwt_secret_key="test-secret-key-for-pytest-only",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        auth_users_json="{}",
    )

    from backend.app.core.config import get_settings

    app.dependency_overrides[get_settings] = lambda: test_settings

    client = TestClient(app)
    return client, test_settings


def test_register_and_login_flow():
    client, settings = make_test_client()

    # Register a new user
    resp = client.post("/auth/register", json={"username": "alice", "password": "s3cret"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice"
    assert "user_id" in body

    # Ensure settings were updated in-memory
    users = json.loads(settings.auth_users_json)
    assert "alice" in users

    # Now login with form-encoded credentials
    login_resp = client.post("/auth/login", data={"username": "alice", "password": "s3cret"})
    assert login_resp.status_code == 200
    token = login_resp.json().get("access_token")
    assert token and isinstance(token, str)


def test_register_duplicate_username_returns_400():
    client, settings = make_test_client()

    resp1 = client.post("/auth/register", json={"username": "bob", "password": "pw"})
    assert resp1.status_code == 201

    resp2 = client.post("/auth/register", json={"username": "bob", "password": "pw2"})
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]
