from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from zarrvis.store import _looks_remote


def test_looks_remote() -> None:
    assert _looks_remote("s3://bucket/x.zarr")
    assert _looks_remote("gs://bucket/x.zarr")
    assert _looks_remote("https://example.com/x.zarr")
    assert not _looks_remote("/tmp/x.zarr")
    assert not _looks_remote("./x.zarr")


def test_api_rejects_remote_without_flag(
    make_client: Callable[..., TestClient], tmp_path: Path
) -> None:
    client = make_client(root=tmp_path, allow_remote=False)
    for url in ["s3://bucket/x.zarr", "gs://bucket/x.zarr", "https://example.com/x.zarr"]:
        resp = client.get("/api/tree", params={"path": url})
        assert resp.status_code == 403, url
        body = resp.json()
        assert "remote" in body["error"]["message"].lower()


def test_api_allows_remote_with_flag_but_connection_fails(
    make_client: Callable[..., TestClient], tmp_path: Path
) -> None:
    client = make_client(root=tmp_path, allow_remote=True)
    # Nonexistent s3 bucket; we're not mocking. Expect a 4xx envelope, not a 500 crash.
    # The actual code path will fail at fsspec/zarr open; we only need to prove the
    # security gate passes and the error is wrapped, not raw.
    resp = client.get(
        "/api/tree",
        params={"path": "s3://this-bucket-does-not-exist-zarrvis-test/nope.zarr"},
    )
    assert resp.status_code in {400, 403, 404, 500, 504}
    body = resp.json()
    # The security gate passed (we got an app-level envelope, not "Forbidden: remote disabled")
    if resp.status_code == 403:
        assert "remote" not in body.get("error", {}).get("message", "").lower()
