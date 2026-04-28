from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Stats:
    count: int
    finite: int
    vmin: float
    vmax: float
    p02: float
    p98: float
    histogram: list[int]
    bin_edges: list[float]


def compute_stats(data: np.ndarray, bins: int = 64) -> Stats:
    arr = np.asarray(data, dtype="float32").ravel()
    finite_mask = np.isfinite(arr)
    finite = arr[finite_mask]
    count = int(arr.size)
    if finite.size == 0:
        return Stats(
            count=count,
            finite=0,
            vmin=0.0,
            vmax=0.0,
            p02=0.0,
            p98=0.0,
            histogram=[0] * bins,
            bin_edges=[0.0] * (bins + 1),
        )
    vmin = float(np.min(finite))
    vmax = float(np.max(finite))
    p02, p98 = (float(x) for x in np.percentile(finite, [2.0, 98.0]))
    if vmax == vmin:
        edges = np.linspace(vmin - 0.5, vmax + 0.5, bins + 1)
    else:
        edges = np.linspace(vmin, vmax, bins + 1)
    hist, _ = np.histogram(finite, bins=edges)
    return Stats(
        count=count,
        finite=int(finite.size),
        vmin=vmin,
        vmax=vmax,
        p02=p02,
        p98=p98,
        histogram=[int(x) for x in hist.tolist()],
        bin_edges=[float(x) for x in edges.tolist()],
    )


def to_dict(stats: Stats) -> dict[str, Any]:
    return asdict(stats)
