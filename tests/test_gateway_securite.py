"""Tests complémentaires : erreurs backend masquées et configuration absente."""
import httpx
from fastapi.testclient import TestClient

from gateway import main as gateway

client = TestClient(gateway.app)
TOKEN = gateway.GATEWAY_TOKEN or "ci-test-token"


def test_backend_unavailable_returns_502_without_details(monkeypatch):
    monkeypatch.setattr(gateway, "GATEWAY_TOKEN", TOKEN)
    monkeypatch.setattr(gateway, "USERS_SERVICE", "http://127.0.0.1:9")

    response = client.get("/users", headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.status_code == 502
    assert response.json() == {"detail": "A backend service is unavailable"}


def test_missing_gateway_token_configuration(monkeypatch):
    monkeypatch.setattr(gateway, "GATEWAY_TOKEN", "")

    response = client.get("/users", headers={"Authorization": "Bearer x"})

    assert response.status_code == 500
    assert "configured" in response.json()["detail"]


def test_fetch_json_uses_timeout(monkeypatch):
    seen = {}
    real_client = httpx.AsyncClient

    def spy(*args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return real_client(*args, **kwargs)

    monkeypatch.setattr(gateway.httpx, "AsyncClient", spy)
    monkeypatch.setattr(gateway, "GATEWAY_TOKEN", TOKEN)
    monkeypatch.setattr(gateway, "USERS_SERVICE", "http://127.0.0.1:9")

    client.get("/users", headers={"Authorization": f"Bearer {TOKEN}"})

    assert seen["timeout"] == 5.0
