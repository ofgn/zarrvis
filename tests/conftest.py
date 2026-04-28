from __future__ import annotations

import secrets
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import zarr
from fastapi.testclient import TestClient

from zarrvis.app import create_app


@pytest.fixture
def token() -> str:
    return secrets.token_urlsafe(16)


@pytest.fixture
def make_client(tmp_path: Path, token: str) -> Callable[..., TestClient]:
    def _factory(
        *,
        root: Path | None = None,
        allow_remote: bool = False,
        initial_path: str | None = None,
    ) -> TestClient:
        app = create_app(
            root=root or tmp_path,
            token=token,
            initial_path=initial_path,
            allow_remote=allow_remote,
        )
        client = TestClient(app)
        client.headers.update({"x-zarrvis-token": token, "host": "127.0.0.1"})
        return client

    return _factory


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


@pytest.fixture
def zarr_v3_store(tmp_path: Path) -> Path:
    """A small zarr v3 store with a 3-D float32 array."""
    path = tmp_path / "v3.zarr"
    arr = zarr.create_array(
        store=str(path),
        shape=(8, 32, 32),
        chunks=(4, 16, 16),
        dtype="float32",
        zarr_format=3,
    )
    data = np.arange(8 * 32 * 32, dtype="float32").reshape(8, 32, 32)
    arr[:] = data
    return path


@pytest.fixture
def zarr_v2_store(tmp_path: Path) -> Path:
    """A small zarr v2 store with a 2-D int16 array under a group."""
    path = tmp_path / "v2.zarr"
    grp = zarr.open_group(store=str(path), mode="w", zarr_format=2)
    arr = grp.create_array(
        name="img",
        shape=(64, 48),
        chunks=(32, 24),
        dtype="int16",
    )
    arr[:] = np.arange(64 * 48, dtype="int16").reshape(64, 48)
    return path


@pytest.fixture
def xarray_zarr_v3(tmp_path: Path) -> Path:
    """An xarray-written zarr v3 store with coords."""
    import xarray as xr

    p = tmp_path / "xr.zarr"
    ds = xr.Dataset(
        {"t2m": (("time", "lat", "lon"), np.random.RandomState(0).randn(3, 5, 7).astype("f4"))},
        coords={
            "time": np.array(["2020-01-01", "2020-02-01", "2020-03-01"], dtype="datetime64[ns]"),
            "lat": np.linspace(-10.0, 10.0, 5),
            "lon": np.linspace(0.0, 180.0, 7),
        },
    )
    ds.to_zarr(p, mode="w", zarr_format=3, consolidated=False)
    return p


@pytest.fixture
def xarray_zarr_v2(tmp_path: Path) -> Path:
    """An xarray-written zarr v2 store (uses _ARRAY_DIMENSIONS)."""
    import xarray as xr

    p = tmp_path / "xr2.zarr"
    ds = xr.Dataset(
        {"t2m": (("time", "lat", "lon"), np.random.RandomState(1).randn(2, 4, 6).astype("f4"))},
        coords={
            "time": np.array(["2020-01-01", "2020-02-01"], dtype="datetime64[ns]"),
            "lat": np.linspace(-5.0, 5.0, 4),
            "lon": np.linspace(0.0, 100.0, 6),
        },
    )
    ds.to_zarr(p, mode="w", zarr_format=2, consolidated=False)
    return p


@pytest.fixture
def zarr_nan_store(tmp_path: Path) -> Path:
    path = tmp_path / "nan.zarr"
    arr = zarr.create_array(
        store=str(path), shape=(16, 16), chunks=(8, 8), dtype="float32", zarr_format=3
    )
    data = np.arange(256, dtype="float32").reshape(16, 16)
    data[0, 0] = np.nan
    data[15, 15] = np.inf
    arr[:] = data
    return path
