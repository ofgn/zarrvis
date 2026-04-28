from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient


def test_tree_v3_array(
    make_client: Callable[..., TestClient], tmp_path: Path, zarr_v3_store: Path
) -> None:
    client = make_client(root=tmp_path)
    resp = client.get("/api/tree", params={"path": str(zarr_v3_store)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tree"]["kind"] == "array"
    assert body["tree"]["shape"] == [8, 32, 32]


def test_tree_v2_group(
    make_client: Callable[..., TestClient], tmp_path: Path, zarr_v2_store: Path
) -> None:
    client = make_client(root=tmp_path)
    resp = client.get("/api/tree", params={"path": str(zarr_v2_store)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tree"]["kind"] == "group"
    names = [c["name"] for c in body["tree"]["children"]]
    assert "img" in names


def test_tree_path_escape_rejected(make_client: Callable[..., TestClient], tmp_path: Path) -> None:
    outside = tmp_path.parent / "far-away"
    outside.mkdir(exist_ok=True)
    client = make_client(root=tmp_path)
    resp = client.get("/api/tree", params={"path": str(outside)})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "Forbidden"


def test_tree_missing_path(make_client: Callable[..., TestClient], tmp_path: Path) -> None:
    client = make_client(root=tmp_path)
    resp = client.get("/api/tree", params={"path": str(tmp_path / "nope.zarr")})
    assert resp.status_code == 404


def test_tree_remote_requires_flag(make_client: Callable[..., TestClient], tmp_path: Path) -> None:
    client = make_client(root=tmp_path)
    resp = client.get("/api/tree", params={"path": "s3://bucket/x.zarr"})
    assert resp.status_code == 403
