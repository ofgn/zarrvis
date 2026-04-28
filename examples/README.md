# Example zarr stores

Five synthetic zarrs to explore with `zarrvis`:

| File | Shape | Dtype | What it exercises |
|---|---|---|---|
| `rings.zarr` | (64, 256, 256) | float32 | 3-D stack, z-scrubbing, auto-contrast |
| `climate.zarr` | (24, 181, 361) | float32 + xarray | coord-aware axis labels, time slider showing dates |
| `microscopy.zarr` | (3, 16, 256, 256) | uint16 | 4-D sliders (channel + z), integer dtype |
| `complex_wave.zarr` | (256, 256) | complex64 | complex rendered as magnitude |
| `with_nans.zarr` | (128, 128) | float32 | NaN → transparent pixels |

## Generate them

```bash
uv run python examples/build_examples.py
```

This writes to `examples/stores/`. Pass a different directory to override:

```bash
uv run python examples/build_examples.py /tmp/zarrvis_stores
```

## Open in zarrvis

Open one store, then swap between the others via the **path input** at the top
of the UI (type a path, press Enter):

```bash
uv run zarrvis examples/stores/climate.zarr
```

`zarrvis` prints a URL with a session token; open it in your browser. The
path input accepts any path under the CLI's `--root` allowlist (default: the
parent of the first store), so you can quickly swap between all five
examples without restarting the server.

## What to try

- On **climate.zarr**, note the axis labels switch to `lat`/`lon` (not `axis 1`/`axis 2`), and the time slider shows dates like `2024-01-15`.
- On **rings.zarr**, drag the z slider fast — you should see in-flight requests cancel (no stale frames).
- On **microscopy.zarr**, swap the "row axis" picker to `z` (axis 1) to look at an orthogonal section.
- On **complex_wave.zarr**, the info strip shows `complex dtype renders as magnitude`.
- On **with_nans.zarr**, change the colormap to `RdBu_r` — the NaN mask stays transparent.
