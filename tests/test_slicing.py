from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import zarr

from zarrvis.errors import BadRequest, OutOfRange, Unsupported
from zarrvis.slicing import (
    SliceRequest,
    compute_slice,
    decode_frame,
    encode_frame,
    parse_axes,
    parse_indices,
)
from zarrvis.store import open_store, resolve_array


def test_parse_indices_default() -> None:
    assert parse_indices(None, 3) == (None, None, None)


def test_parse_indices_json() -> None:
    assert parse_indices("[0, null, 2]", 3) == (0, None, 2)


def test_parse_indices_wrong_length() -> None:
    with pytest.raises(BadRequest):
        parse_indices("[0, 1]", 3)


def test_parse_indices_invalid_json() -> None:
    with pytest.raises(BadRequest):
        parse_indices("not json", 3)


def test_parse_axes_default() -> None:
    assert parse_axes(None, 4) == (2, 3)


def test_parse_axes_json() -> None:
    assert parse_axes("[1, 3]", 4) == (1, 3)


def test_parse_axes_same_axis() -> None:
    with pytest.raises(BadRequest):
        parse_axes("[1, 1]", 4)


def test_parse_axes_out_of_range() -> None:
    with pytest.raises(OutOfRange):
        parse_axes("[0, 5]", 4)


def test_compute_slice_default_axes(zarr_v3_store: Path) -> None:
    arr = resolve_array(open_store(zarr_v3_store), "/")
    req = SliceRequest(indices=(3, None, None), axes=(1, 2), max_px=1024)
    data, header = compute_slice(arr, req)
    assert data.shape == (32, 32)
    assert data.dtype == np.float32
    # Cross-check: we sliced z=3 out of arange(8*32*32)
    expected = np.arange(8 * 32 * 32).reshape(8, 32, 32)[3].astype("float32")
    assert np.array_equal(data, expected)
    assert header["rows"] == 32
    assert header["cols"] == 32
    assert header["vmin"] == float(expected.min())
    assert header["vmax"] == float(expected.max())


def test_compute_slice_transposed(zarr_v3_store: Path) -> None:
    arr = resolve_array(open_store(zarr_v3_store), "/")
    req = SliceRequest(indices=(3, None, None), axes=(2, 1), max_px=1024)
    data, _ = compute_slice(arr, req)
    expected = np.arange(8 * 32 * 32).reshape(8, 32, 32)[3].T.astype("float32")
    assert np.array_equal(data, expected)


def test_compute_slice_downsample() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "big.zarr"
        arr = zarr.create_array(
            store=str(p), shape=(2000, 2000), chunks=(200, 200), dtype="float32", zarr_format=3
        )
        arr[:] = np.arange(2000 * 2000, dtype="float32").reshape(2000, 2000)
        a = resolve_array(open_store(p), "/")
        req = SliceRequest(indices=(None, None), axes=(0, 1), max_px=512)
        data, header = compute_slice(a, req)
        # ceil(2000/512) = 4 stride → ceil(2000/4) = 500 rows
        assert header["strides"] == [4, 4]
        assert data.shape == (500, 500)


def test_compute_slice_index_out_of_range(zarr_v3_store: Path) -> None:
    arr = resolve_array(open_store(zarr_v3_store), "/")
    req = SliceRequest(indices=(99, None, None), axes=(1, 2), max_px=1024)
    with pytest.raises(OutOfRange):
        compute_slice(arr, req)


def test_compute_slice_index_on_plotted_axis(zarr_v3_store: Path) -> None:
    arr = resolve_array(open_store(zarr_v3_store), "/")
    req = SliceRequest(indices=(3, 0, None), axes=(1, 2), max_px=1024)
    with pytest.raises(BadRequest):
        compute_slice(arr, req)


def test_compute_slice_nan_and_inf(zarr_nan_store: Path) -> None:
    arr = resolve_array(open_store(zarr_nan_store), "/")
    req = SliceRequest(indices=(None, None), axes=(0, 1), max_px=1024)
    data, header = compute_slice(arr, req)
    assert np.isnan(data[0, 0])
    assert np.isinf(data[15, 15])
    assert math_finite(header["vmin"]) and math_finite(header["vmax"])


def math_finite(v: float) -> bool:
    import math as _m

    return _m.isfinite(v)


def test_compute_slice_1d_rejected(tmp_path: Path) -> None:
    p = tmp_path / "one.zarr"
    arr = zarr.create_array(store=str(p), shape=(10,), chunks=(10,), dtype="f4", zarr_format=3)
    arr[:] = np.arange(10, dtype="f4")
    a = resolve_array(open_store(p), "/")
    req = SliceRequest(indices=(None,), axes=(0, 0), max_px=1024)
    with pytest.raises(Unsupported):
        compute_slice(a, req)


def test_compute_slice_int_to_float(zarr_v2_store: Path) -> None:
    arr = resolve_array(open_store(zarr_v2_store), "/img")
    req = SliceRequest(indices=(None, None), axes=(0, 1), max_px=1024)
    data, _ = compute_slice(arr, req)
    assert data.dtype == np.float32


def test_encode_decode_roundtrip() -> None:
    data = np.random.RandomState(0).randn(17, 23).astype("float32")
    header = {"rows": 17, "cols": 23, "dtype": "float32", "foo": [1, 2, 3]}
    frame = encode_frame(data, header)
    dec, h = decode_frame(frame)
    assert h["rows"] == 17
    assert h["foo"] == [1, 2, 3]
    assert np.array_equal(dec, data)
