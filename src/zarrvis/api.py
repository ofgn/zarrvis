from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from zarrvis import __version__
from zarrvis.errors import BadRequest, NotFound
from zarrvis.security import validate_path
from zarrvis.slicing import SliceRequest, compute_slice, encode_frame, parse_axes, parse_indices
from zarrvis.stats import compute_stats, to_dict
from zarrvis.store import (
    assert_renderable,
    coord_to_json_values,
    extract_dims,
    find_coord_array,
    info_to_dict,
    open_store,
    resolve_array,
    walk_tree,
)

logger = logging.getLogger(__name__)


def _resolve(request: Request, path: str) -> str:
    resolved = validate_path(
        path,
        root=request.app.state.root,
        allow_remote=request.app.state.allow_remote,
    )
    return str(resolved)


def build_api_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health(request: Request) -> dict[str, object]:
        return {
            "status": "ok",
            "version": __version__,
            "root": str(request.app.state.root),
            "allow_remote": bool(request.app.state.allow_remote),
            "initial_path": request.app.state.initial_path,
            "time": time.time(),
        }

    @router.get("/tree")
    async def tree(
        request: Request,
        path: str = Query(..., description="Path to the zarr store."),
    ) -> dict[str, Any]:
        resolved = _resolve(request, path)
        started = time.perf_counter()
        root = open_store(resolved)
        info = walk_tree(root)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("tree(%s) %.1fms", resolved, elapsed_ms)
        return {"path": resolved, "tree": info_to_dict(info)}

    @router.get("/slice")
    async def slice_endpoint(
        request: Request,
        path: str = Query(...),
        array: str = Query("/", description="Path within the store."),
        indices: str | None = Query(None, description="JSON list; null = plotted axis."),
        axes: str | None = Query(None, description="JSON list of two axis indices."),
        max_px: int = Query(1024, ge=1, le=8192),
        level: int = Query(0, ge=0),
    ) -> Response:
        resolved = _resolve(request, path)
        started = time.perf_counter()
        root = open_store(resolved)
        arr = resolve_array(root, array)
        assert_renderable(arr)
        req = SliceRequest(
            indices=parse_indices(indices, arr.ndim),
            axes=parse_axes(axes, arr.ndim),
            max_px=max_px,
            level=level,
        )
        data, header = compute_slice(arr, req)
        frame = encode_frame(data, header)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "slice(%s%s) %dx%d %.1fms %d bytes",
            resolved,
            array,
            header["rows"],
            header["cols"],
            elapsed_ms,
            len(frame),
        )
        return Response(
            content=frame,
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "no-store",
                "X-ZarrVis-Rows": str(header["rows"]),
                "X-ZarrVis-Cols": str(header["cols"]),
            },
        )

    @router.get("/coords")
    async def coords_endpoint(
        request: Request,
        path: str = Query(...),
        array: str = Query(...),
        axis: int = Query(..., ge=0),
    ) -> dict[str, Any]:
        resolved = _resolve(request, path)
        root = open_store(resolved)
        arr = resolve_array(root, array)
        if not (0 <= axis < arr.ndim):
            raise BadRequest(f"axis {axis} out of range for ndim={arr.ndim}")
        dims = extract_dims(arr)
        if not dims:
            raise NotFound(f"array has no dimension names; cannot resolve coord for axis {axis}")
        dim_name = dims[axis]
        coord = find_coord_array(root, array, dim_name)
        if coord is None:
            return {"dim": dim_name, "axis": axis, "length": int(arr.shape[axis]), "values": None}
        values, dtype = coord_to_json_values(coord)
        return {
            "dim": dim_name,
            "axis": axis,
            "length": int(coord.shape[0]),
            "dtype": dtype,
            "values": values,
        }

    @router.get("/stats")
    async def stats_endpoint(
        request: Request,
        path: str = Query(...),
        array: str = Query("/"),
        indices: str | None = Query(None),
        axes: str | None = Query(None),
        max_px: int = Query(512, ge=1, le=8192),
    ) -> dict[str, Any]:
        resolved = _resolve(request, path)
        root = open_store(resolved)
        arr = resolve_array(root, array)
        assert_renderable(arr)
        req = SliceRequest(
            indices=parse_indices(indices, arr.ndim),
            axes=parse_axes(axes, arr.ndim),
            max_px=max_px,
        )
        data, header = compute_slice(arr, req)
        stats = compute_stats(data)
        return {"path": resolved, "array": array, "header": header, "stats": to_dict(stats)}

    return router
