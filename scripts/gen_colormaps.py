"""Regenerate the vendored colormap LUTs.

Usage (from the repo root):

    uvx --with matplotlib --from matplotlib python scripts/gen_colormaps.py

Writes src/zarrvis/colormap.py and src/zarrvis/static/colormaps.js in place.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.cm as cm
import numpy as np

NAMES = ["viridis", "magma", "inferno", "gray", "RdBu_r", "turbo"]
REPO = Path(__file__).resolve().parents[1]


def _chunked(flat, per_line=24):
    for i in range(0, len(flat), per_line):
        yield ", ".join(str(x) for x in flat[i : i + per_line])


def sample() -> dict[str, list[list[int]]]:
    out: dict[str, list[list[int]]] = {}
    for name in NAMES:
        cmap = cm.get_cmap(name, 256)
        rgba = (cmap(np.arange(256))[:, :3] * 255).round().astype("uint8")
        out[name] = rgba.tolist()
    return out


def write_python(data: dict[str, list[list[int]]]) -> None:
    out = [
        '"""Colormap lookup tables (256x3 uint8).',
        "",
        "Sourced from matplotlib 3.x (see THIRD_PARTY.md).",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import numpy as np",
        "",
        "# fmt: off",
        "COLORMAPS: dict[str, np.ndarray] = {}",
        "",
    ]
    for name in NAMES:
        flat = [v for rgb in data[name] for v in rgb]
        out.append(f'COLORMAPS["{name}"] = np.array([')
        for line in _chunked(flat):
            out.append(f"    {line},")
        out.append("], dtype=np.uint8).reshape(256, 3)")
        out.append("")
    out += [
        "# fmt: on",
        "",
        "",
        "def names() -> list[str]:",
        "    return list(COLORMAPS.keys())",
        "",
        "",
        "def apply(data: np.ndarray, vmin: float, vmax: float, name: str) -> np.ndarray:",
        '    """Map a 2-D float array to RGBA uint8 using the named colormap."""',
        "    if name not in COLORMAPS:",
        '        raise KeyError(f"unknown colormap: {name}")',
        "    lut = COLORMAPS[name]",
        "    span = vmax - vmin if vmax > vmin else 1.0",
        "    nan_mask = ~np.isfinite(data)",
        "    safe = np.where(nan_mask, vmin, data)",
        "    scaled = (safe - vmin) / span",
        "    idx = np.clip(np.rint(scaled * 255.0), 0, 255).astype(np.int32)",
        "    rgb = lut[idx]",
        "    alpha = np.where(nan_mask, 0, 255).astype(np.uint8)[..., None]",
        "    return np.concatenate([rgb, alpha], axis=-1)",
        "",
    ]
    (REPO / "src/zarrvis/colormap.py").write_text("\n".join(out))


def write_js(data: dict[str, list[list[int]]]) -> None:
    out = ["// Colormap lookup tables (256x3 uint8). See THIRD_PARTY.md.", ""]
    out.append(f"export const COLORMAP_NAMES = {json.dumps(NAMES)};")
    out.append("")
    out.append("export const COLORMAPS = {};")
    for name in NAMES:
        flat = [v for rgb in data[name] for v in rgb]
        out.append(f"COLORMAPS[{json.dumps(name)}] = new Uint8Array([")
        for line in _chunked(flat):
            out.append(f"    {line},")
        out.append("]);")
        out.append("")
    (REPO / "src/zarrvis/static/colormaps.js").write_text("\n".join(out))


def main() -> None:
    data = sample()
    write_python(data)
    write_js(data)
    print(f"wrote {len(NAMES)} colormaps to src/zarrvis/")


if __name__ == "__main__":
    main()
