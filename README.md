# zarrvis

[![CI](https://github.com/OWNER/zarrvis/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/zarrvis/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A clean, production-ready, sleek browser visualization of [zarr](https://zarr.dev/) files.

Point `zarrvis` at a local or remote zarr store and get a dark, modern web UI with
a zarr tree, axis/slider controls, colormaps, contrast, and an interactive image
view. Handles generic n-D arrays and labeled
[xarray](https://xarray.dev/) / [OME-Zarr](https://ngff.openmicroscopy.org/) stores.

## Features

- **Any zarr store** — reads zarr v2 and v3, consolidated or not.
- **Any shape** — 2D, 3D, 4D, …; sliders for every non-plotted axis, swap the row/column axis at will.
- **xarray / geospatial aware** — uses `dimension_names` (zarr v3) and `_ARRAY_DIMENSIONS` (v2); shows coordinate values next to sliders and as plot tick labels.
- **Sleek, responsive UI** — dark theme, Inter font, Plotly-powered pan/zoom; contrast and colormap changes are instant (no round-trip).
- **Fast** — server streams a compact binary float32 frame; the browser does colormap + contrast with no refetch.
- **Safe by default** — localhost-only, path allowlist, DNS-rebinding guard, per-session URL token.
- **Remote stores** — `s3://`, `gs://`, `https://` behind `--allow-remote`, with an automatic on-disk fsspec cache.
- **Shareable views** — the URL encodes the current array, axes, indices, colormap, and contrast.
- **Lean install** — runtime deps: `fastapi`, `uvicorn`, `zarr>=3`, `xarray`, `fsspec`, `numpy`.

## Install

Requires Python 3.12+.

```bash
uv tool install zarrvis                 # recommended
# or, from a clone:
uv sync
uv run zarrvis --help
```

For remote stores:

```bash
uv tool install 'zarrvis[remote]'
```

## Use

```bash
zarrvis /path/to/store.zarr
```

`zarrvis` prints a localhost URL with a session token and tries to open your
browser. The UI shows the zarr tree on the left and a viewer on the right.
Click any renderable array to plot it; drag sliders to scrub through
non-plotted axes; swap the row/column axis to re-slice.

### CLI

```
zarrvis [PATH] [--host 127.0.0.1] [--port 8765]
        [--root ROOT] [--allow-remote] [--no-browser] [--verbose]
```

- `PATH` — a zarr store directory (or an fsspec URL with `--allow-remote`). If omitted, open the UI and paste a path in the header input.
- `--root` — allowlist root for local paths (default: parent of `PATH`, or `$HOME`).
- `--allow-remote` — permit `s3://`, `gs://`, `https://` URLs.
- `--port` — if busy, zarrvis falls back to an OS-assigned port.
- `--verbose` — enable DEBUG logging + uvicorn access logs.

### Shareable URLs

The URL in the address bar encodes the current view. Copy it and send to a
teammate running `zarrvis` on the same machine; they'll land on the same
array, slice, colormap, and contrast.

## Supported data

| Kind                  | Status          | Notes |
|-----------------------|-----------------|-------|
| `float16/32/64`       | ✅              |
| `int*/uint*`          | ✅              | upcast to float32 on the wire |
| `bool`                | ✅              | rendered 0/1 |
| `datetime64`          | ✅              | rendered as seconds-since-epoch; coord values shown as ISO strings |
| `complex64/128`       | ⚠️ magnitude    | rendered as `\|z\|` with a hint in the info strip |
| `object` / strings    | ❌ unsupported  | not visualizable; tree shows the reason |

## API

All routes live under `/api/*`, require a per-session token, and sit behind a
`Host` header guard.

| Route | Returns |
|---|---|
| `GET /api/health` | status + version + allowlist info |
| `GET /api/tree?path=…` | tree of groups/arrays with shape, dtype, chunks, shards, dims, attrs |
| `GET /api/slice?path=…&array=…&indices=…&axes=…&max_px=1024` | binary `[u32][json header][float32 payload]` frame |
| `GET /api/stats?…` | NaN-aware percentiles (2/98), min/max, 64-bin histogram |
| `GET /api/coords?path=…&array=…&axis=…` | coord-array values for the given axis (if present) |

The slice wire format is deliberately simple so you can call it from Python
scripts:

```python
import httpx, struct, json, numpy as np

r = httpx.get(
    "http://127.0.0.1:8765/api/slice",
    params={"path": "/data/store.zarr", "indices": "[3, null, null]", "token": TOKEN},
)
buf = r.content
(hlen,) = struct.unpack("<I", buf[:4])
header = json.loads(buf[4:4 + hlen])
data = np.frombuffer(buf[4 + hlen:], dtype="float32").reshape(header["rows"], header["cols"])
```

## Security model

zarrvis is designed to be safe to run on your laptop, not to be exposed to
the internet.

- Binds `127.0.0.1` only.
- Every `/api/*` request requires a random per-session token that is baked
  into the URL printed by the CLI.
- `Host` headers other than `localhost`/`127.0.0.1`/`::1` are rejected (DNS
  rebinding defense).
- The `path` parameter is resolved and checked against an allowlist root
  (default: parent of the CLI `PATH` argument, or `$HOME`).
- Remote (`s3://`, `gs://`, `http(s)://`) URLs require an explicit
  `--allow-remote` flag.

## Development

```bash
git clone https://github.com/OWNER/zarrvis && cd zarrvis
uv sync --all-extras --dev
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run ty check src/zarrvis          # alpha type checker; advisory
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contributor guide.

## Roadmap

- **v1.1** — OME-Zarr multiscale pyramid level selection (viewport-aware)
- **v1.2** — PNG export + server-rendered thumbnail cache for the tree
- **v1.3** — Label-layer overlays for OME-Zarr segmentation masks

## License

[MIT](LICENSE). Colormap LUTs are derived from [matplotlib](https://matplotlib.org/)
— see [THIRD_PARTY.md](THIRD_PARTY.md).
