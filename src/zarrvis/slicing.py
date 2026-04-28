"""n-D array slicing with stride downsampling and binary framing.

Wire format for a 2-D slice returned by /api/slice:

    [u32 header_len][json header bytes][float32 payload bytes]

The JSON header is UTF-8 and carries `rows`, `cols`, `stride`, axes, indices,
and min/max of the payload (NaN-safe). The payload is C-contiguous float32.

``header_len`` is always a multiple of 4 (the JSON is right-padded with
trailing spaces if needed) so that the float32 payload begins at a 4-byte
aligned offset. That lets the browser construct ``new Float32Array(buffer,
offset, length)`` without copying.
"""

from __future__ import annotations

import json
import logging
import math
import struct
from dataclasses import dataclass
from typing import Any

import numpy as np
import zarr

from zarrvis.errors import BadRequest, OutOfRange, Unsupported

logger = logging.getLogger(__name__)

MAX_PX_CEILING = 8192


@dataclass(frozen=True)
class SliceRequest:
    indices: tuple[int | None, ...]
    axes: tuple[int, int]
    max_px: int = 1024
    level: int = 0


def parse_indices(raw: str | None, ndim: int) -> tuple[int | None, ...]:
    """Parse indices from a JSON list. ``null`` marks the plotted axes."""
    if raw is None or raw == "":
        return tuple([None] * ndim)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BadRequest(f"indices is not valid JSON: {exc}") from exc
    if not isinstance(parsed, list) or len(parsed) != ndim:
        raise BadRequest(f"indices must be a JSON list of length {ndim}")
    out: list[int | None] = []
    for v in parsed:
        if v is None:
            out.append(None)
        elif isinstance(v, int):
            out.append(v)
        elif isinstance(v, float) and v.is_integer():
            out.append(int(v))
        else:
            raise BadRequest("indices entries must be integers or null")
    return tuple(out)


def parse_axes(raw: str | None, ndim: int) -> tuple[int, int]:
    if raw is None or raw == "":
        if ndim < 2:
            raise BadRequest("array has fewer than 2 dimensions; cannot plot")
        # default: last two axes
        return (ndim - 2, ndim - 1)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BadRequest(f"axes is not valid JSON: {exc}") from exc
    if not isinstance(parsed, list) or len(parsed) != 2:
        raise BadRequest("axes must be a JSON list of two integers")
    try:
        a, b = int(parsed[0]), int(parsed[1])
    except (TypeError, ValueError) as exc:
        raise BadRequest("axes entries must be integers") from exc
    if a == b:
        raise BadRequest("axes entries must be distinct")
    if not (0 <= a < ndim and 0 <= b < ndim):
        raise OutOfRange(f"axis out of range for ndim={ndim}: {parsed}")
    return (a, b)


def _clamp_max_px(max_px: int) -> int:
    if max_px <= 0:
        raise BadRequest("max_px must be positive")
    return min(int(max_px), MAX_PX_CEILING)


def _validate_indices(
    shape: tuple[int, ...], indices: tuple[int | None, ...], axes: tuple[int, int]
) -> None:
    for i, (extent, idx) in enumerate(zip(shape, indices, strict=True)):
        if i in axes:
            if idx is not None:
                raise BadRequest(f"axis {i} is a plotted axis; indices[{i}] must be null")
        else:
            if idx is None:
                raise BadRequest(f"axis {i} is not plotted; indices[{i}] must be an int")
            if not (0 <= idx < extent):
                raise OutOfRange(f"index {idx} out of range for axis {i} (extent {extent})")


def _stride_for(extent: int, max_px: int) -> int:
    return max(1, math.ceil(extent / max_px))


def _build_slicers(
    shape: tuple[int, ...],
    indices: tuple[int | None, ...],
    axes: tuple[int, int],
    max_px: int,
) -> tuple[tuple[slice | int, ...], int, int]:
    row_axis, col_axis = axes
    row_stride = _stride_for(shape[row_axis], max_px)
    col_stride = _stride_for(shape[col_axis], max_px)
    slicers: list[slice | int] = []
    for i, extent in enumerate(shape):
        if i == row_axis:
            slicers.append(slice(0, extent, row_stride))
        elif i == col_axis:
            slicers.append(slice(0, extent, col_stride))
        else:
            idx = indices[i]
            assert idx is not None  # validated earlier
            slicers.append(idx)
    return tuple(slicers), row_stride, col_stride


def _to_float32_2d(sliced: np.ndarray, axes: tuple[int, int]) -> np.ndarray:
    """Cast to float32 and orient so returned shape is (rows, cols)."""
    arr = np.asarray(sliced)
    if arr.ndim != 2:
        raise BadRequest(f"internal: expected 2-D slice, got shape {arr.shape}")
    if arr.dtype.kind == "c":
        arr = np.abs(arr)
    if arr.dtype.kind == "M":  # datetime64 → float seconds since epoch
        arr = arr.astype("datetime64[ns]").astype("int64").astype("float32") / 1e9
    elif arr.dtype.kind == "m":  # timedelta64
        arr = arr.astype("timedelta64[ns]").astype("int64").astype("float32") / 1e9
    elif arr.dtype.kind == "b":
        arr = arr.astype("float32")
    arr = arr.astype("float32", copy=False)
    # If the row_axis index > col_axis index, the squeezed order is (col, row),
    # so transpose to make the output (row_axis, col_axis).
    if axes[0] > axes[1]:
        arr = arr.T
    return np.ascontiguousarray(arr)


def compute_slice(arr: zarr.Array, req: SliceRequest) -> tuple[np.ndarray, dict[str, Any]]:
    if arr.ndim < 2:
        raise Unsupported("arrays with fewer than 2 dimensions are not renderable")
    max_px = _clamp_max_px(req.max_px)
    _validate_indices(arr.shape, req.indices, req.axes)
    slicers, row_stride, col_stride = _build_slicers(arr.shape, req.indices, req.axes, max_px)
    raw = arr[slicers]
    data = _to_float32_2d(np.asarray(raw), req.axes)
    finite = np.isfinite(data)
    if finite.any():
        vmin = float(np.min(data, where=finite, initial=np.inf))
        vmax = float(np.max(data, where=finite, initial=-np.inf))
    else:
        vmin = 0.0
        vmax = 0.0
    header = {
        "rows": int(data.shape[0]),
        "cols": int(data.shape[1]),
        "dtype": "float32",
        "axes": list(req.axes),
        "indices": [None if v is None else int(v) for v in req.indices],
        "strides": [int(row_stride), int(col_stride)],
        "original_shape": [int(x) for x in arr.shape],
        "source_dtype": str(arr.dtype),
        "vmin": vmin,
        "vmax": vmax,
        "level": int(req.level),
    }
    return data, header


def encode_frame(data: np.ndarray, header: dict[str, Any]) -> bytes:
    payload = data.astype("float32", copy=False).tobytes(order="C")
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    pad = (-len(header_bytes)) % 4
    if pad:
        header_bytes = header_bytes + b" " * pad
    return struct.pack("<I", len(header_bytes)) + header_bytes + payload


def decode_frame(buf: bytes) -> tuple[np.ndarray, dict[str, Any]]:
    """Inverse of :func:`encode_frame`. Used by tests and Python clients."""
    if len(buf) < 4:
        raise ValueError("frame too short")
    (header_len,) = struct.unpack("<I", buf[:4])
    header_end = 4 + header_len
    header = json.loads(buf[4:header_end].decode("utf-8"))
    payload = np.frombuffer(buf[header_end:], dtype="float32").reshape(
        header["rows"], header["cols"]
    )
    return payload, header
