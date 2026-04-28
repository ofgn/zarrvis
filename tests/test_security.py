from __future__ import annotations

from pathlib import Path

import pytest

from zarrvis.errors import Forbidden, NotFound
from zarrvis.security import resolve_local_path, validate_path


def test_resolve_local_path_within_root(tmp_path: Path) -> None:
    f = tmp_path / "data.zarr"
    f.mkdir()
    resolved = resolve_local_path(str(f), tmp_path)
    assert resolved == f.resolve()


def test_resolve_local_path_escape_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "elsewhere"
    outside.mkdir(exist_ok=True)
    with pytest.raises(Forbidden):
        resolve_local_path(str(outside), tmp_path)


def test_resolve_local_path_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope.zarr"
    with pytest.raises(NotFound):
        resolve_local_path(str(missing), tmp_path)


def test_validate_remote_requires_flag(tmp_path: Path) -> None:
    with pytest.raises(Forbidden):
        validate_path("s3://bucket/x.zarr", root=tmp_path, allow_remote=False)


def test_validate_remote_allowed(tmp_path: Path) -> None:
    out = validate_path("s3://bucket/x.zarr", root=tmp_path, allow_remote=True)
    assert out == "s3://bucket/x.zarr"
