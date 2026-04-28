# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "playwright>=1.48",
#     "httpx>=0.27",
# ]
# ///
"""Capture screenshots of zarrvis against the example stores.

Boots a zarrvis server, drives a headless Chromium through fixed view-state
URLs, and writes PNGs to docs/screenshots/.

Usage (from the repo root):

    uv run scripts/screenshot.py

The script uses PEP 723 inline metadata, so `uv run` resolves Playwright on
the fly. The first run also downloads Chromium (~150 MB) via
`playwright install chromium`; subsequent runs reuse the cached browser.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import httpx
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
STORES = REPO / "examples" / "stores"
OUT = REPO / "docs" / "screenshots"
# Stores are copied here before the screenshot run so the path shown in the
# zarrvis address bar is a neutral location, not the user's home directory.
STAGE = Path("/tmp/zarrvis-demo/stores")

VIEWPORT = {"width": 1440, "height": 900}
DEVICE_SCALE = 2


@dataclass
class Shot:
    name: str
    store: str
    indices: list[int | None]
    axes: list[int]
    cmap: str
    max_px: int = 1024


SHOTS: list[Shot] = [
    Shot(
        "hero",
        "air_temperature.zarr",
        indices=[0, None, None],
        axes=[1, 2],
        cmap="RdBu_r",
    ),
    Shot("rasm", "rasm.zarr", indices=[0, None, None], axes=[1, 2], cmap="viridis"),
    Shot(
        "eraint",
        "eraint_uvz.zarr",
        indices=[0, 1, None, None],
        axes=[2, 3],
        cmap="RdBu_r",
    ),
    Shot("ersst", "ersstv5.zarr", indices=[600, None, None], axes=[1, 2], cmap="RdBu_r"),
]


def ensure_examples() -> None:
    if STORES.exists() and any(STORES.iterdir()):
        return
    print("examples/stores/ missing — running build_examples.py", flush=True)
    subprocess.run([sys.executable, str(REPO / "examples" / "build_examples.py")], check=True)


def stage_stores() -> None:
    """Mirror referenced stores into STAGE so screenshots show a neutral path."""
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    for shot in SHOTS:
        src = STORES / shot.store
        if not src.exists():
            continue
        shutil.copytree(src, STAGE / shot.store)


def ensure_chromium() -> None:
    """Download Chromium if Playwright doesn't have it yet."""
    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return
    except Exception:
        pass
    print("installing Playwright Chromium (~150 MB, one-time)…", flush=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_health(base: str, token: str, timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base}/api/health", params={"token": token}, timeout=1.0)
            if r.status_code == 200:
                return
        except Exception as exc:
            last_exc = exc
        time.sleep(0.1)
    raise RuntimeError(f"zarrvis did not come up in {timeout_s}s: {last_exc}")


def resolve_array_path(base: str, token: str, store_path: Path) -> str:
    """Return the path of the highest-dimensional renderable array (ndim >= 2).

    Prefers higher-rank arrays so that xarray stores (which expose 1-D coord
    arrays alongside the data variable) pick the data variable, not a coord.
    """
    r = httpx.get(
        f"{base}/api/tree",
        params={"path": str(store_path), "token": token},
        timeout=10.0,
    )
    r.raise_for_status()
    tree = r.json()["tree"]

    candidates: list[tuple[int, str]] = []

    def walk(node: dict) -> None:
        if node.get("kind") == "array" and node.get("renderable"):
            ndim = len(node.get("shape", []) or [])
            if ndim >= 2:
                candidates.append((ndim, node["path"]))
        for child in node.get("children", []) or []:
            walk(child)

    walk(tree)
    if not candidates:
        raise RuntimeError(f"no renderable >=2-D array in {store_path}")
    candidates.sort(reverse=True)
    return candidates[0][1]


def build_url(base: str, token: str, store_path: Path, array: str, shot: Shot) -> str:
    qs = urlencode(
        {
            "token": token,
            "path": str(store_path),
            "array": array,
            "axes": json.dumps(shot.axes),
            "indices": json.dumps(shot.indices),
            "cmap": shot.cmap,
            "maxPx": shot.max_px,
        }
    )
    return f"{base}/?{qs}"


def start_zarrvis(port: int) -> tuple[subprocess.Popen[str], str]:
    """Start zarrvis pointed at the staged stores; return (proc, token).

    Invokes the project venv's zarrvis via `uv run` rather than `sys.executable`,
    because this PEP 723 script runs in its own ephemeral environment that does
    not have zarrvis installed.
    """
    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "--project",
            str(REPO),
            "zarrvis",
            str(STAGE),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-browser",
            "--root",
            str(STAGE),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ},
    )
    token = ""
    deadline = time.monotonic() + 15
    assert proc.stdout is not None
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError("zarrvis exited before printing URL")
            continue
        if "url" in line and "token=" in line:
            token = line.split("token=")[-1].strip()
            break
    if not token:
        proc.terminate()
        raise RuntimeError("did not see zarrvis URL in stdout")
    return proc, token


def main() -> int:
    ensure_examples()
    stage_stores()
    ensure_chromium()

    OUT.mkdir(parents=True, exist_ok=True)
    port = free_port()
    base = f"http://127.0.0.1:{port}"

    proc, token = start_zarrvis(port)
    try:
        wait_for_health(base, token)
        print(f"zarrvis up on {base}", flush=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport=VIEWPORT,
                device_scale_factor=DEVICE_SCALE,
            )
            page = context.new_page()

            for shot in SHOTS:
                store_path = STAGE / shot.store
                if not store_path.exists():
                    print(f"skip {shot.name}: {store_path} missing", flush=True)
                    continue
                array = resolve_array_path(base, token, store_path)
                url = build_url(base, token, store_path, array, shot)
                print(f"  {shot.name:12s} → {shot.store}  array={array}", flush=True)

                page.goto(url, wait_until="networkidle")
                page.wait_for_selector(".js-plotly-plot", state="visible", timeout=10_000)
                page.wait_for_function(
                    "() => !!document.querySelector('.js-plotly-plot .main-svg')",
                    timeout=10_000,
                )
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(400)

                out = OUT / f"{shot.name}.png"
                page.screenshot(path=str(out), full_page=False)
                print(f"    wrote {out.relative_to(REPO)}", flush=True)

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
