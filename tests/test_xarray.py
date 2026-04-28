from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from zarrvis.store import (
    coord_to_json_values,
    extract_dims,
    find_coord_array,
    open_store,
    resolve_array,
    walk_tree,
)


def test_extract_dims_v3(xarray_zarr_v3: Path) -> None:
    arr = resolve_array(open_store(xarray_zarr_v3), "/t2m")
    assert extract_dims(arr) == ["time", "lat", "lon"]


def test_extract_dims_v2(xarray_zarr_v2: Path) -> None:
    arr = resolve_array(open_store(xarray_zarr_v2), "/t2m")
    assert extract_dims(arr) == ["time", "lat", "lon"]


def test_walk_exposes_dims(xarray_zarr_v3: Path) -> None:
    info = walk_tree(open_store(xarray_zarr_v3))
    t2m = next(c for c in info.children if c.name == "t2m")
    assert t2m.dims == ["time", "lat", "lon"]


def test_find_coord_array_numeric(xarray_zarr_v3: Path) -> None:
    root = open_store(xarray_zarr_v3)
    lat = find_coord_array(root, "/t2m", "lat")
    assert lat is not None
    values, dtype = coord_to_json_values(lat)
    assert len(values) == 5
    assert dtype == "float64"
    assert values[0] == -10.0
    assert values[-1] == 10.0


def test_find_coord_array_time(xarray_zarr_v3: Path) -> None:
    root = open_store(xarray_zarr_v3)
    time = find_coord_array(root, "/t2m", "time")
    assert time is not None
    values, dtype = coord_to_json_values(time)
    # xarray writes time as int with CF units, so coord values here are raw
    # ints, not decoded datetimes. Ensure the module doesn't crash on them.
    assert len(values) == 3
    assert dtype in {"int64", "datetime64"}


def test_api_coords(
    make_client: Callable[..., TestClient], tmp_path: Path, xarray_zarr_v3: Path
) -> None:
    client = make_client(root=tmp_path)
    resp = client.get(
        "/api/coords",
        params={"path": str(xarray_zarr_v3), "array": "/t2m", "axis": "1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dim"] == "lat"
    assert body["length"] == 5
    assert body["values"][0] == -10.0


def test_api_coords_missing_dims(
    make_client: Callable[..., TestClient], tmp_path: Path, zarr_v3_store: Path
) -> None:
    client = make_client(root=tmp_path)
    resp = client.get(
        "/api/coords",
        params={"path": str(zarr_v3_store), "array": "/", "axis": "0"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NotFound"


def test_api_coords_out_of_range(
    make_client: Callable[..., TestClient], tmp_path: Path, xarray_zarr_v3: Path
) -> None:
    client = make_client(root=tmp_path)
    resp = client.get(
        "/api/coords",
        params={"path": str(xarray_zarr_v3), "array": "/t2m", "axis": "99"},
    )
    assert resp.status_code == 400
