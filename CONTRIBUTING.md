# Contributing

ZarrVis is small and tries to stay that way. Bug fixes and patches that cut
complexity are very welcome.

## Setup

```bash
git clone https://github.com/ofgn/zarrvis && cd zarrvis
uv sync --all-extras --dev
uv run pytest -q
```

## Stack

- **uv** for envs and deps; `uv.lock` is committed.
- **ruff** for lint and format.
- **pytest** with `fastapi.testclient.TestClient` for the API tests.
- **ty** (Astral, alpha). CI runs it as advisory.

## Layout

```
src/zarrvis/
    cli.py             argparse, port fallback, token, browser open
    app.py             FastAPI factory, static mount
    api.py             /api/* routes
    store.py           zarr + xarray + fsspec; tree walk, dim/coord resolution
    slicing.py         n-D indexing, stride downsample, binary framing
    stats.py           NaN-aware percentiles, histogram
    colormap.py        6 vendored LUTs + numpy apply()
    security.py        path allowlist, host-header guard, token middleware
    errors.py          exception hierarchy + FastAPI handlers
    static/            single page, ES module, no build step
tests/                 conftest builds synthetic zarrs; unit + API tests
```

## Frontend

No build step. `static/app.js` is a native ES module loaded by
`index.html`. Plotly and the Inter font come from CDNs (MIT and SIL OFL).

## Backend

A throwaway store to iterate against:

```bash
uv run python -c "import numpy as np, zarr; a = zarr.create_array(store='/tmp/demo.zarr', shape=(32,256,256), chunks=(8,64,64), dtype='f4', zarr_format=3, overwrite=True); a[:] = np.random.randn(32,256,256).astype('f4')"
uv run zarrvis /tmp/demo.zarr --verbose
```

New API routes need at least:

1. A happy-path test through `TestClient`.
2. A sad-path test verifying the error envelope (`{"error": {"code", "message", "hint"}}`).

## Style

- `from __future__ import annotations`; type-annotate public functions.
- Comments only when the *why* is non-obvious.
- User-visible errors go through `ZarrVisError` so they surface as proper
  envelopes with typed codes.
- Don't add runtime deps lightly. If matplotlib / pillow / etc. would
  simplify something, see if a 30-line vendor works first
  (e.g. `colormap.py`).

## Regenerating colormap LUTs

```bash
uvx --with matplotlib --from matplotlib python scripts/gen_colormaps.py
```

Writes to `src/zarrvis/colormap.py` and `src/zarrvis/static/colormaps.js`.

## CI

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs lint, tests
(py3.12 / 3.13 × Linux / macOS / Windows), `ty` (advisory), and a wheel/sdist
build.

## Releasing

1. Bump `version` in [pyproject.toml](pyproject.toml).
2. `git tag vX.Y.Z && git push --tags`.
