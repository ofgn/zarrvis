from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from zarrvis.slicing import decode_frame


def test_slice_default(
    make_client: Callable[..., TestClient], tmp_path: Path, zarr_v3_store: Path
) -> None:
    client = make_client(root=tmp_path)
    resp = client.get(
        "/api/slice",
        params={"path": str(zarr_v3_store), "indices": "[3, null, null]"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    assert resp.headers["x-zarrvis-rows"] == "32"
    assert resp.headers["x-zarrvis-cols"] == "32"
    data, header = decode_frame(resp.content)
    assert data.shape == (32, 32)
    expected = np.arange(8 * 32 * 32).reshape(8, 32, 32)[3].astype("float32")
    assert np.array_equal(data, expected)
    assert header["source_dtype"] == "float32"


def test_slice_array_subpath(
    make_client: Callable[..., TestClient], tmp_path: Path, zarr_v2_store: Path
) -> None:
    client = make_client(root=tmp_path)
    resp = client.get(
        "/api/slice",
        params={"path": str(zarr_v2_store), "array": "/img"},
    )
    assert resp.status_code == 200
    data, _header = decode_frame(resp.content)
    assert data.shape == (64, 48)


def test_slice_bad_indices(
    make_client: Callable[..., TestClient], tmp_path: Path, zarr_v3_store: Path
) -> None:
    client = make_client(root=tmp_path)
    resp = client.get(
        "/api/slice",
        params={"path": str(zarr_v3_store), "indices": "[99, null, null]"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OutOfRange"


def test_slice_downsample_max_px(make_client: Callable[..., TestClient], tmp_path: Path) -> None:
    import zarr

    p = tmp_path / "big.zarr"
    arr = zarr.create_array(
        store=str(p), shape=(1200, 1200), chunks=(300, 300), dtype="f4", zarr_format=3
    )
    arr[:] = 0.0
    client = make_client(root=tmp_path)
    resp = client.get(
        "/api/slice",
        params={"path": str(p), "max_px": "400"},
    )
    assert resp.status_code == 200
    data, header = decode_frame(resp.content)
    assert header["strides"] == [3, 3]
    assert data.shape == (400, 400)


def test_stats_endpoint(
    make_client: Callable[..., TestClient], tmp_path: Path, zarr_v3_store: Path
) -> None:
    client = make_client(root=tmp_path)
    resp = client.get(
        "/api/stats",
        params={"path": str(zarr_v3_store), "indices": "[3, null, null]"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stats"]["finite"] == 32 * 32
    assert (
        body["stats"]["vmin"]
        <= body["stats"]["p02"]
        <= body["stats"]["p98"]
        <= body["stats"]["vmax"]
    )
    assert len(body["stats"]["histogram"]) == 64
    assert len(body["stats"]["bin_edges"]) == 65
