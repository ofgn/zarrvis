from __future__ import annotations

import numpy as np
import pytest

from zarrvis.colormap import COLORMAPS, apply, names


def test_all_luts_loaded() -> None:
    assert set(names()) == {"viridis", "magma", "inferno", "gray", "RdBu_r", "turbo"}
    for lut in COLORMAPS.values():
        assert lut.shape == (256, 3)
        assert lut.dtype == np.uint8


def test_gray_linear_mapping() -> None:
    data = np.array([[0.0, 0.5, 1.0]], dtype="float32")
    rgba = apply(data, 0.0, 1.0, "gray")
    assert rgba[0, 0, 0] == 0
    assert rgba[0, 2, 0] == 255
    assert 120 <= rgba[0, 1, 0] <= 135  # ~mid-grey


def test_nan_becomes_transparent() -> None:
    data = np.array([[0.0, np.nan]], dtype="float32")
    rgba = apply(data, 0.0, 1.0, "viridis")
    assert rgba[0, 0, 3] == 255
    assert rgba[0, 1, 3] == 0  # transparent


def test_alpha_channel_and_clip() -> None:
    data = np.array([[-10.0, 0.0, 1.0, 10.0]], dtype="float32")
    rgba = apply(data, 0.0, 1.0, "viridis")
    assert tuple(rgba[0, 0, :3]) == tuple(rgba[0, 1, :3])  # clamped low
    assert tuple(rgba[0, 3, :3]) == tuple(rgba[0, 2, :3])  # clamped high
    assert rgba.dtype == np.uint8


def test_unknown_colormap_raises() -> None:
    with pytest.raises(KeyError):
        apply(np.zeros((2, 2), dtype="float32"), 0.0, 1.0, "bogus")


def test_flat_range_does_not_crash() -> None:
    data = np.zeros((4, 4), dtype="float32")
    rgba = apply(data, 0.0, 0.0, "viridis")
    assert rgba.shape == (4, 4, 4)
