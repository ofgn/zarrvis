# ZarrVis

[![CI](https://github.com/ofgn/zarrvis/actions/workflows/ci.yml/badge.svg)](https://github.com/ofgn/zarrvis/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A small browser viewer for zarr files. Reads zarr v2 and v3, plain n-D arrays
or labelled [xarray](https://xarray.dev/) /
[OME-Zarr](https://ngff.openmicroscopy.org/) stores. Local paths or remote
`s3://` / `gs://` / `https://` URLs.

![ERA-Interim global geopotential height with the turbo colormap](docs/screenshots/hero.png)

## Status

Experimental (v0.1.0). Probably has rough edges. If you hit one, please
[open an issue](https://github.com/ofgn/zarrvis/issues). A `zarr.tree()`
dump and the `--verbose` traceback are usually enough.

## Install

```bash
uv tool install zarrvis              # local stores
uv tool install 'zarrvis[remote]'    # also s3/gs/https
```

Python 3.12+.

## Use

```bash
zarrvis /path/to/store.zarr
```

Prints a `http://127.0.0.1:…/?token=…` URL and opens your browser. Click an
array in the tree to plot it, drag the sliders to scrub other axes, change
the row / column axis to re-slice. The URL encodes the view, so you can
copy-paste it.

```
zarrvis [PATH] [--host 127.0.0.1] [--port 8765]
        [--root ROOT] [--allow-remote] [--no-browser] [--verbose]
```

`--root` defaults to the parent of `PATH` (or `$HOME`). Remote URLs need
`--allow-remote`.

## Gallery

| RASM Arctic Tair | NOAA ERSST v5 | NCEP air temperature |
|---|---|---|
| ![](docs/screenshots/rasm.png) | ![](docs/screenshots/ersst.png) | ![](docs/screenshots/air_temperature.png) |
| Regional Arctic surface air temperature, ocean NaN | Global sea-surface temperature, land NaN | NCEP/NCAR reanalysis 2-m air temp over North America |

All four shots are real datasets pulled from the xarray tutorial mirror by
[examples/build_examples.py](examples/build_examples.py). Reproduce with
`uv run scripts/screenshot.py`.

## Supported dtypes

| Kind | Status | Notes |
|---|---|---|
| `float16/32/64` | works | |
| `int*` / `uint*` | works | sent to the browser as float32 |
| `bool` | works | 0/1 |
| `datetime64` | works | rendered as seconds-since-epoch |
| `complex64/128` | partial | rendered as `\|z\|` |
| `object` / strings | no | tree shows why |

## Development

```bash
git clone https://github.com/ofgn/zarrvis && cd zarrvis
uv sync --all-extras --dev
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## What's next

OME-Zarr multiscale (viewport-aware level pick), an on-disk cache for async
cloud filesystems, PNG export, label-layer overlays.

## License

[MIT](LICENSE). Colormap LUTs are from [matplotlib](https://matplotlib.org/),
see [THIRD_PARTY.md](THIRD_PARTY.md).
