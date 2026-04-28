from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import zarr

from zarrvis.errors import BadRequest, NotFound
from zarrvis.store import (
    info_to_dict,
    open_store,
    resolve_array,
    walk_tree,
)


def test_open_v3_store(zarr_v3_store: Path) -> None:
    root = open_store(zarr_v3_store)
    assert isinstance(root, zarr.Array)
    assert root.shape == (8, 32, 32)


def test_open_v2_group(zarr_v2_store: Path) -> None:
    root = open_store(zarr_v2_store)
    assert isinstance(root, zarr.Group)
    names = [n for n, _ in root.members()]
    assert "img" in names


def test_open_missing(tmp_path: Path) -> None:
    with pytest.raises(NotFound):
        open_store(tmp_path / "does-not-exist.zarr")


def test_walk_v3_array(zarr_v3_store: Path) -> None:
    info = walk_tree(open_store(zarr_v3_store))
    d = info_to_dict(info)
    assert d["kind"] == "array"
    assert d["shape"] == [8, 32, 32]
    assert d["dtype"] == "float32"
    assert d["chunks"] == [4, 16, 16]
    assert d["renderable"] is True


def test_walk_v2_group(zarr_v2_store: Path) -> None:
    info = walk_tree(open_store(zarr_v2_store))
    d = info_to_dict(info)
    assert d["kind"] == "group"
    child = next(c for c in d["children"] if c["name"] == "img")
    assert child["kind"] == "array"
    assert child["shape"] == [64, 48]
    assert child["dtype"] == "int16"


def test_walk_nested(tmp_path: Path) -> None:
    p = tmp_path / "nested.zarr"
    g = zarr.open_group(str(p), mode="w", zarr_format=3)
    g.create_array(name="top", shape=(4,), chunks=(4,), dtype="f4")
    sub = g.create_group("sub")
    sub.create_array(name="inner", shape=(3, 3), chunks=(3, 3), dtype="i4")
    info = walk_tree(open_store(p))
    d = info_to_dict(info)
    assert d["kind"] == "group"
    by_name = {c["name"]: c for c in d["children"]}
    assert set(by_name) == {"top", "sub"}
    inner = next(c for c in by_name["sub"]["children"] if c["name"] == "inner")
    assert inner["path"] == "/sub/inner"


def test_resolve_array(zarr_v2_store: Path) -> None:
    root = open_store(zarr_v2_store)
    arr = resolve_array(root, "/img")
    assert arr.shape == (64, 48)


def test_resolve_array_missing(zarr_v2_store: Path) -> None:
    root = open_store(zarr_v2_store)
    with pytest.raises(NotFound):
        resolve_array(root, "/nope")


def test_resolve_array_on_root_array(zarr_v3_store: Path) -> None:
    root = open_store(zarr_v3_store)
    arr = resolve_array(root, "/")
    assert arr.shape == (8, 32, 32)


def test_resolve_group_not_array(tmp_path: Path) -> None:
    p = tmp_path / "g.zarr"
    g = zarr.open_group(str(p), mode="w", zarr_format=3)
    g.create_group("sub")
    root = open_store(p)
    with pytest.raises(BadRequest):
        resolve_array(root, "/sub")


def test_unsupported_dtype(tmp_path: Path) -> None:
    p = tmp_path / "obj.zarr"
    # string dtype
    arr = zarr.create_array(store=str(p), shape=(2,), chunks=(2,), dtype="<U4", zarr_format=3)
    arr[:] = np.array(["foo", "bar"], dtype="<U4")
    info = walk_tree(open_store(p))
    d = info_to_dict(info)
    assert d["renderable"] is False
    assert "not renderable" in d["unsupported_reason"]


def test_array_dimensions_attr(tmp_path: Path) -> None:
    p = tmp_path / "xr.zarr"
    g = zarr.open_group(str(p), mode="w", zarr_format=3)
    arr = g.create_array(name="t", shape=(4, 5), chunks=(4, 5), dtype="f4")
    arr.attrs["_ARRAY_DIMENSIONS"] = ["y", "x"]
    info = walk_tree(open_store(p))
    d = info_to_dict(info)
    child = next(c for c in d["children"] if c["name"] == "t")
    assert child["dims"] == ["y", "x"]


def test_multiscales_flag(tmp_path: Path) -> None:
    p = tmp_path / "ms.zarr"
    g = zarr.open_group(str(p), mode="w", zarr_format=3)
    g.attrs["multiscales"] = [{"datasets": [{"path": "0"}]}]
    info = walk_tree(open_store(p))
    d = info_to_dict(info)
    assert d["has_multiscales"] is True
