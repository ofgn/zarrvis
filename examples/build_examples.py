"""Generate a handful of example zarr stores for exploring zarrvis.

Usage (from the repo root):

    uv run python examples/build_examples.py            # writes into examples/stores/
    uv run python examples/build_examples.py /path/to   # writes into /path/to/

Then:

    uv run zarrvis examples/stores/
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import xarray as xr
import zarr

HERE = Path(__file__).resolve().parent


def _out(base: Path, name: str) -> str:
    p = base / name
    if p.exists():
        import shutil

        shutil.rmtree(p)
    return str(p)


def rings(base: Path) -> None:
    """3-D concentric rings — lets you scrub z and see the pattern evolve."""
    path = _out(base, "rings.zarr")
    nz, ny, nx = 64, 256, 256
    arr = zarr.create_array(
        store=path, shape=(nz, ny, nx), chunks=(8, 64, 64), dtype="float32", zarr_format=3
    )
    y, x = np.mgrid[:ny, :nx]
    cy, cx = ny / 2, nx / 2
    r = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    for z in range(nz):
        arr[z] = np.sin(0.18 * r - 0.2 * z).astype("float32") + 0.15 * np.random.randn(
            ny, nx
        ).astype("float32")
    print(f"  wrote {path}")


def climate(base: Path) -> None:
    """xarray climate cube (time, lat, lon) with real coords."""
    path = _out(base, "climate.zarr")
    n_time = 24
    lat = np.linspace(-90, 90, 181)
    lon = np.linspace(-180, 180, 361)
    lat_grid, lon_grid = np.meshgrid(lat, lon, indexing="ij")
    base_temp = (
        15
        + 25 * np.cos(np.deg2rad(lat_grid))
        - 0.05 * np.abs(lat_grid)
        + 3 * np.sin(np.deg2rad(lon_grid / 2))
    )
    data = np.empty((n_time, lat.size, lon.size), dtype="float32")
    for i in range(n_time):
        seasonal = 6 * np.sin(2 * np.pi * i / 12) * np.sign(lat_grid)
        noise = np.random.RandomState(i).randn(lat.size, lon.size).astype("float32") * 0.8
        data[i] = (base_temp + seasonal + noise).astype("float32")
    times = np.array(
        [f"2024-{((i % 12) + 1):02d}-15" for i in range(n_time)], dtype="datetime64[ns]"
    )
    ds = xr.Dataset(
        {
            "t2m": (
                ("time", "lat", "lon"),
                data,
                {"units": "degC", "long_name": "2m air temperature"},
            )
        },
        coords={"time": times, "lat": lat, "lon": lon},
        attrs={"source": "zarrvis synthetic example", "variable": "t2m"},
    )
    ds.to_zarr(path, mode="w", zarr_format=3, consolidated=False)
    print(f"  wrote {path}  (xarray, 24 x 181 x 361 float32)")


def microscopy(base: Path) -> None:
    """Multi-channel z-stack reminiscent of fluorescence microscopy."""
    path = _out(base, "microscopy.zarr")
    nc, nz, ny, nx = 3, 16, 256, 256
    arr = zarr.create_array(
        store=path, shape=(nc, nz, ny, nx), chunks=(1, 4, 64, 64), dtype="uint16", zarr_format=3
    )
    # zarr-v3 dimension_names on the underlying metadata
    y, x = np.mgrid[:ny, :nx]
    for c in range(nc):
        cy = ny * (0.3 + 0.2 * c)
        cx = nx * (0.3 + 0.25 * c)
        for z in range(nz):
            r2 = (y - cy) ** 2 + (x - cx) ** 2
            falloff = np.exp(-r2 / (2 * (30 + 2 * z) ** 2))
            noise = np.random.RandomState(c * 100 + z).randint(0, 200, size=(ny, nx))
            frame = (2000 * falloff + noise).clip(0, 65535).astype("uint16")
            arr[c, z] = frame
    arr.attrs["_ARRAY_DIMENSIONS"] = ["channel", "z", "y", "x"]
    print(f"  wrote {path}  (3 x 16 x 256 x 256 uint16)")


def complex_magnitude(base: Path) -> None:
    """Complex-valued array — zarrvis renders the magnitude."""
    path = _out(base, "complex_wave.zarr")
    ny, nx = 256, 256
    y, x = np.mgrid[:ny, :nx]
    wave = np.exp(1j * (0.1 * x + 0.05 * y))
    arr = zarr.create_array(
        store=path, shape=(ny, nx), chunks=(64, 64), dtype="complex64", zarr_format=3
    )
    arr[:] = wave.astype("complex64")
    print(f"  wrote {path}  (complex64 — rendered as magnitude)")


def nan_mask(base: Path) -> None:
    """2-D array with NaNs — should render as transparent pixels."""
    path = _out(base, "with_nans.zarr")
    ny, nx = 128, 128
    y, x = np.mgrid[:ny, :nx]
    data = np.sin(0.15 * x) * np.cos(0.2 * y).astype("float32")
    mask = (y - ny / 2) ** 2 + (x - nx / 2) ** 2 > (ny / 2) ** 2
    data = data.astype("float32")
    data[mask] = np.nan
    arr = zarr.create_array(
        store=path, shape=(ny, nx), chunks=(32, 32), dtype="float32", zarr_format=3
    )
    arr[:] = data
    print(f"  wrote {path}  (NaN outside circle)")


def main() -> None:
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "stores"
    base.mkdir(parents=True, exist_ok=True)
    print(f"building examples in {base}")
    rings(base)
    climate(base)
    microscopy(base)
    complex_magnitude(base)
    nan_mask(base)
    print("done.")
    print("\ntry:")
    print(f"  uv run zarrvis {base}")


if __name__ == "__main__":
    main()
