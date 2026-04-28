from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["allow_remote"] is False


def test_token_required_on_api(make_client: Callable[..., TestClient]) -> None:
    client = make_client()
    client.headers.pop("x-zarrvis-token", None)
    resp = client.get("/api/health")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "Unauthorized"


def test_token_via_query_param(make_client: Callable[..., TestClient], token: str) -> None:
    client = make_client()
    client.headers.pop("x-zarrvis-token", None)
    resp = client.get("/api/health", params={"token": token})
    assert resp.status_code == 200


def test_wrong_token_rejected(make_client: Callable[..., TestClient]) -> None:
    client = make_client()
    client.headers["x-zarrvis-token"] = "nope"
    resp = client.get("/api/health")
    assert resp.status_code == 401


def test_host_header_guard(client: TestClient) -> None:
    resp = client.get("/api/health", headers={"host": "evil.example.com"})
    assert resp.status_code == 421
    assert resp.json()["error"]["code"] == "Forbidden"


def test_localhost_host_allowed(client: TestClient) -> None:
    resp = client.get("/api/health", headers={"host": "localhost:8765"})
    assert resp.status_code == 200


def test_index_served(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "zarrvis" in resp.text.lower()
