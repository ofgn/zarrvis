# Example zarr stores

Nine zarrs to play with. Four real (xarray-data tutorial mirror), five
synthetic.

| File | Shape | Dtype | Notes |
|---|---|---|---|
| `air_temperature.zarr` | (2920, 25, 53) | int16, xarray | NCEP/NCAR reanalysis 2-m air temperature over North America |
| `rasm.zarr` | (36, 205, 275) | float64, xarray | RASM regional Arctic surface air temperature; ocean is NaN |
| `eraint_uvz.zarr` | (2, 3, 241, 480) | float64, xarray | ERA-Interim global geopotential and winds, `(month, level, lat, lon)` |
| `ersstv5.zarr` | (624, 89, 180) | float32, xarray | NOAA Extended Reconstructed SST v5; land is NaN |
| `rings.zarr` | (64, 256, 256) | float32 | synthetic 3-D stack |
| `climate.zarr` | (24, 181, 361) | float32, xarray | synthetic xarray dataset with `lat`/`lon` coords |
| `microscopy.zarr` | (3, 16, 256, 256) | uint16 | synthetic 4-D, `(channel, z, y, x)` |
| `complex_wave.zarr` | (256, 256) | complex64 | rendered as magnitude |
| `with_nans.zarr` | (128, 128) | float32 | synthetic circular NaN mask |

The real-data fetches need the dev extras (`pooch` + `netcdf4`); without
them, those four are skipped with a hint and the synthetic ones still build.

## Generate

```bash
uv run python examples/build_examples.py             # → examples/stores/
uv run python examples/build_examples.py /tmp/out    # → /tmp/out/
```

## Open

```bash
uv run zarrvis examples/stores/air_temperature.zarr
```

The path input at the top of the UI accepts any path under the CLI's
`--root` allowlist, so you can swap between stores without restarting.

## Things to try

- `air_temperature.zarr`: scrub `time` and watch the seasonal pattern shift.
- `ersstv5.zarr` (`/sst`): pick `RdBu_r`, scrub `time` over the 624 monthly
  steps, watch the ENSO Pacific tongue come and go.
- `rasm.zarr` (`/Tair`): the ocean NaN mask renders the coastline.
- `eraint_uvz.zarr`: 4-D, so you get sliders for both `month` and `level`.
- `rings.zarr`: drag the z slider fast; in-flight requests cancel, no
  stale frames.
- `microscopy.zarr`: switch the row-axis picker to `z` for an orthogonal
  section.
