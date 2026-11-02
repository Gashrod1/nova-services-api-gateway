import os

from fastapi.testclient import TestClient

from gateway import main as gateway

TOKEN = os.getenv("GATEWAY_TOKEN", "ci-test-token")

gateway.GATEWAY_TOKEN = TOKEN

client = TestClient(gateway.app)


def test_health_is_public():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_users_requires_authentication():
    response = client.get("/users")

    assert response.status_code == 401


def test_users_with_invalid_token():
    response = client.get(
        "/users",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_profile_aggregates_user_and_orders(monkeypatch):
    async def fake_fetch_json(url):
        if url.endswith("/users"):
            return [
                {"id": 1, "name": "Alice", "email": "alice@test.com"},
                {"id": 2, "name": "Bob", "email": "bob@test.com"},
            ]

        if url.endswith("/orders"):
            return [
                {"id": 101, "userId": 1, "item": "Laptop"},
                {"id": 102, "userId": 2, "item": "Phone"},
                {"id": 103, "userId": 1, "item": "Keyboard"},
            ]

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(gateway, "fetch_json", fake_fetch_json)

    response = client.get(
        "/profile/1",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user"]["id"] == 1
    assert [order["id"] for order in data["orders"]] == [101, 103]


def test_profile_unknown_user(monkeypatch):
    async def fake_fetch_json(url):
        if url.endswith("/users"):
            return [{"id": 1, "name": "Alice", "email": "alice@test.com"}]

        return [{"id": 101, "userId": 1, "item": "Laptop"}]

    monkeypatch.setattr(gateway, "fetch_json", fake_fetch_json)

    response = client.get(
        "/profile/999",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 404
