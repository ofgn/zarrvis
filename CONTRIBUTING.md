# Contributing to zarrvis

Thanks for considering a contribution! zarrvis aims to stay small, legible,
and production-ready. Patches that reduce complexity are as valuable as new
features.

## Dev setup

```bash
git clone https://github.com/OWNER/zarrvis && cd zarrvis
uv sync --all-extras --dev
uv run pytest -q
```

## Stack

- **uv** — env + dependency manager. Commit `uv.lock`.
- **ruff** — lint + format. `uv run ruff check . && uv run ruff format .`.
- **pytest** — tests, with `fastapi.testclient.TestClient` for API tests.
- **ty** — Astral's type checker, currently alpha. CI runs it with
  `continue-on-error`; failures are advisory.

## Layout

```
src/zarrvis/
    __init__.py        # version + public surface
    __main__.py        # python -m zarrvis
    cli.py             # argparse, port fallback, token, browser open
    app.py             # FastAPI factory, static mount
    api.py             # /api/* routes
    store.py           # zarr + xarray + fsspec; tree walk, dim & coord resolution
    slicing.py         # n-D indexing, stride downsample, binary framing
    stats.py           # NaN-aware percentiles + histogram
    colormap.py        # 6 vendored LUTs + numpy apply()
    security.py        # path allowlist, host-header guard, token middleware
    errors.py          # exception hierarchy + FastAPI handlers
    static/
        index.html     # single page + importmap
        app.js         # module; tree, sliders, canvas colormap, URL state
        app.css        # dark theme
        colormaps.js   # same LUTs as colormap.py (emitted together)
tests/                 # conftest.py builds synthetic zarrs; unit + API tests
```

## Working on the frontend

There is **no build step** — `static/app.js` is a native ES module loaded
by `index.html`. Edit, refresh, move on. Plotly and Inter font load from CDN
(MIT / SIL OFL respectively); no npm.

## Working on the backend

Run the app against a throwaway store while you iterate:

```bash
uv run python -c "import numpy as np, zarr; a = zarr.create_array(store='/tmp/demo.zarr', shape=(32,256,256), chunks=(8,64,64), dtype='f4', zarr_format=3, overwrite=True); a[:] = np.random.randn(32,256,256).astype('f4')"
uv run zarrvis /tmp/demo.zarr --verbose
```

Add tests for new functionality. New API routes should have at least:

1. A happy-path test hitting the route with `TestClient`.
2. A sad-path test verifying the error envelope (`{"error": {"code", "message", "hint"}}`).

## Style

- Type-annotate public functions; `from __future__ import annotations`.
- No comments unless the *why* is non-obvious — identifiers should carry the *what*.
- Errors the user might hit go through the `ZarrVisError` hierarchy, so they
  surface as proper envelopes and typed codes.
- Don't add runtime deps lightly. If matplotlib / pillow / etc. would simplify
  something, check whether a 30-line vendor works first (see `colormap.py`).

## Regenerating the colormap LUTs

If you ever need to re-vendor the colormaps (e.g. add a new one), the LUTs are
generated once from matplotlib via `uvx`:

```bash
uvx --with matplotlib --from matplotlib python scripts/gen_colormaps.py
```

The output goes to `src/zarrvis/colormap.py` and `src/zarrvis/static/colormaps.js`.

## CI

The GitHub Actions pipeline in [.github/workflows/ci.yml](.github/workflows/ci.yml)
runs lint, tests (across Python 3.12 / 3.13 and Linux / macOS / Windows),
the `ty` type checker (advisory), and a wheel/sdist build.

## Releasing

1. Bump `version` in [pyproject.toml](pyproject.toml).
2. Update the Roadmap section in [README.md](README.md) if needed.
3. `git tag vX.Y.Z && git push --tags` — CI builds and publishes the artifacts.
