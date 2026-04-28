from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import zarr

from zarrvis.errors import BadRequest, NotFound, Unsupported

logger = logging.getLogger(__name__)

Node = zarr.Group | zarr.Array

_UNSUPPORTED_KINDS = {"O", "U", "S", "V"}


@dataclass
class ArrayInfo:
    name: str
    path: str
    shape: tuple[int, ...]
    dtype: str
    chunks: tuple[int, ...] | None
    shards: tuple[int, ...] | None
    dims: list[str] | None
    fill_value: Any
    attrs: dict[str, Any]
    renderable: bool
    unsupported_reason: str | None
    kind: str = "array"


@dataclass
class GroupInfo:
    name: str
    path: str
    attrs: dict[str, Any]
    has_multiscales: bool
    children: list[GroupInfo | ArrayInfo] = field(default_factory=list)
    kind: str = "group"


def _looks_remote(path: str) -> bool:
    return "://" in path


def _remote_mapper(url: str) -> Any:
    """Return an fsspec mapper wrapped in a local cache."""
    import fsspec
    from fsspec.implementations.cached import CachingFileSystem

    cache_dir = Path.home() / ".cache" / "zarrvis" / "fsspec"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        fs, fs_path = fsspec.core.url_to_fs(url)
    except ImportError as exc:
        raise BadRequest(
            f"remote protocol not available: {exc}",
            hint="install the optional [remote] extra: uv pip install 'zarrvis[remote]'",
        ) from exc
    except Exception as exc:
        raise BadRequest(f"cannot parse remote URL: {exc}") from exc
    cached = CachingFileSystem(
        target_protocol=fs.protocol if isinstance(fs.protocol, str) else fs.protocol[0],
        target_options=fs.storage_options,
        cache_storage=str(cache_dir),
    )
    return cached.get_mapper(fs_path)


def open_store(path: str | Path) -> Node:
    """Open a zarr store, preferring consolidated metadata for speed."""
    path_str = str(path)
    store_arg: Any = _remote_mapper(path_str) if _looks_remote(path_str) else path_str
    try:
        return zarr.open_consolidated(store_arg, mode="r")
    except (KeyError, FileNotFoundError, NotImplementedError, ValueError) as exc:
        logger.debug("consolidated open failed (%s); falling back to zarr.open", exc)
    try:
        return zarr.open(store_arg, mode="r")
    except FileNotFoundError as exc:
        raise NotFound(f"zarr store not found: {path}") from exc
    except Exception as exc:
        raise BadRequest(f"failed to open zarr store: {exc}") from exc


def _json_clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_clean(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_json_clean(x) for x in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return f"<{len(obj)} bytes>"
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _dtype_info(arr: zarr.Array) -> tuple[bool, str | None]:
    kind = arr.dtype.kind
    if kind in _UNSUPPORTED_KINDS:
        return False, f"dtype '{arr.dtype}' is not renderable"
    if kind == "c":
        return True, "complex dtype renders as magnitude"
    return True, None


def extract_dims(arr: zarr.Array) -> list[str] | None:
    """Pull dimension names from zarr v3 metadata or the xarray v2 convention."""
    meta = getattr(arr, "metadata", None)
    v3_dims = getattr(meta, "dimension_names", None) if meta is not None else None
    if v3_dims:
        return [str(x) for x in v3_dims if x is not None]
    ad = arr.attrs.get("_ARRAY_DIMENSIONS") if hasattr(arr, "attrs") else None
    if isinstance(ad, list) and ad:
        return [str(x) for x in ad]
    return None


def _array_info(name: str, path: str, arr: zarr.Array) -> ArrayInfo:
    renderable, reason = _dtype_info(arr)
    raw_attrs = dict(arr.attrs)
    dims = extract_dims(arr)

    fill = arr.fill_value
    if isinstance(fill, np.generic):
        fill = fill.item()

    chunks = tuple(int(x) for x in arr.chunks) if arr.chunks else None
    shards_raw = getattr(arr, "shards", None)
    shards = tuple(int(x) for x in shards_raw) if shards_raw else None

    return ArrayInfo(
        name=name,
        path=path,
        shape=tuple(int(x) for x in arr.shape),
        dtype=str(arr.dtype),
        chunks=chunks,
        shards=shards,
        dims=dims,
        fill_value=_json_clean(fill),
        attrs=_json_clean(raw_attrs),
        renderable=renderable,
        unsupported_reason=reason,
    )


def _group_info(name: str, path: str, grp: zarr.Group) -> GroupInfo:
    attrs = _json_clean(dict(grp.attrs))
    return GroupInfo(
        name=name,
        path=path,
        attrs=attrs,
        has_multiscales="multiscales" in attrs,
    )


def _child_path(parent: str, name: str) -> str:
    if parent in ("", "/"):
        return f"/{name}"
    return f"{parent}/{name}"


def walk_tree(root: Node) -> GroupInfo | ArrayInfo:
    if isinstance(root, zarr.Array):
        return _array_info("/", "/", root)

    def _walk(name: str, path: str, node: Node) -> GroupInfo | ArrayInfo:
        if isinstance(node, zarr.Array):
            return _array_info(name, path, node)
        info = _group_info(name, path, node)
        for child_name, child in node.members():
            info.children.append(_walk(child_name, _child_path(path, child_name), child))
        return info

    return _walk("/", "/", root)


def resolve_array(root: Node, array_path: str) -> zarr.Array:
    if isinstance(root, zarr.Array):
        if array_path not in ("/", ""):
            raise NotFound(f"root is an array; unexpected subpath: {array_path}")
        return root
    parts = [p for p in array_path.strip("/").split("/") if p]
    if not parts:
        raise BadRequest("array_path must point to an array, not the root group")
    node: Node = root
    for p in parts:
        try:
            node = node[p]
        except KeyError as exc:
            raise NotFound(f"path not found in store: {array_path}") from exc
    if not isinstance(node, zarr.Array):
        raise BadRequest(f"{array_path} is not an array")
    return node


def info_to_dict(info: GroupInfo | ArrayInfo) -> dict[str, Any]:
    return _json_clean(asdict(info))


def assert_renderable(arr: zarr.Array) -> None:
    renderable, reason = _dtype_info(arr)
    if not renderable:
        raise Unsupported(reason or f"dtype '{arr.dtype}' is not renderable")


def _coord_candidate_paths(array_path: str, dim_name: str) -> list[str]:
    """Paths to search for a coord array named ``dim_name``, parent → root."""
    parts = [p for p in array_path.strip("/").split("/") if p]
    candidates: list[str] = []
    # same group as data array, then ancestors, then root
    for depth in range(len(parts) - 1, -1, -1):
        prefix = "/" + "/".join(parts[:depth]) if depth else ""
        candidates.append(f"{prefix}/{dim_name}".replace("//", "/"))
    return candidates


def find_coord_array(root: Node, array_path: str, dim_name: str) -> zarr.Array | None:
    for candidate in _coord_candidate_paths(array_path, dim_name):
        try:
            node = resolve_array(root, candidate)
        except (NotFound, BadRequest):
            continue
        if node.ndim == 1:
            return node
    return None


def coord_to_json_values(arr: zarr.Array) -> tuple[list[Any], str]:
    """Return (values, rendered_dtype) — strings for datetime, numbers otherwise."""
    data = arr[:]
    kind = arr.dtype.kind
    if kind == "M":
        iso = np.datetime_as_string(data.astype("datetime64[ns]"), unit="auto")
        return [str(x) for x in iso], "datetime64"
    if kind == "m":
        return [float(x) for x in data.astype("timedelta64[ns]").astype("int64")], "timedelta64"
    if kind in {"U", "S"}:
        return [str(x) for x in data.tolist()], str(arr.dtype)
    if kind == "b":
        return [bool(x) for x in data.tolist()], "bool"
    # numeric
    return [float(x) for x in np.asarray(data, dtype="float64").tolist()], str(arr.dtype)
