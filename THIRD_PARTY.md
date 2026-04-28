# Third-party data & code

## Colormap lookup tables

The 256-entry RGB colormap tables vendored in

- [src/zarrvis/colormap.py](src/zarrvis/colormap.py)
- [src/zarrvis/static/colormaps.js](src/zarrvis/static/colormaps.js)

are the `viridis`, `magma`, `inferno`, `gray`, `RdBu_r`, and `turbo` colormaps
from [matplotlib](https://matplotlib.org/), sampled at 256 equally-spaced
points via `matplotlib.cm.get_cmap(name, 256)`. Matplotlib is distributed
under a PSF-based license that permits redistribution; see
<https://matplotlib.org/stable/users/project/license.html>.

The `turbo` colormap was designed by Google (Anton Mikhailov) and donated to
matplotlib. See <https://ai.googleblog.com/2019/08/turbo-improved-rainbow-colormap-for.html>.

## Frontend libraries (loaded at runtime from CDN)

- [Plotly.js](https://plotly.com/javascript/) — MIT. Loaded via
  `cdn.plot.ly` in [src/zarrvis/static/index.html](src/zarrvis/static/index.html).
