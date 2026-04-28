from __future__ import annotations

import argparse
import logging
import secrets
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from zarrvis import __version__

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8765


def _bindable(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
        except OSError:
            return False
        return True


def _resolve_port(host: str, port: int) -> int:
    if port == 0 or _bindable(host, port):
        return port
    logger.warning("port %d is busy; asking OS for a free port", port)
    return 0


def _build_url(host: str, port: int, token: str) -> str:
    return f"http://{host}:{port}/?token={token}"


def _open_browser_soon(url: str, delay: float = 0.6) -> None:
    def _open() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url, new=2)
        except Exception as exc:
            logger.debug("webbrowser.open failed: %s", exc)

    threading.Thread(target=_open, daemon=True).start()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="zarrvis",
        description="Browser viewer for zarr files.",
    )
    parser.add_argument("path", nargs="?", help="Path to a zarr store (local path or fsspec URL).")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Bind port (default: {DEFAULT_PORT})."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Allowlist root for path access (default: parent of PATH, or $HOME).",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Permit fsspec URLs (s3://, gs://, http(s)://).",
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open a browser.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable DEBUG logging.")
    parser.add_argument("--version", action="version", version=f"ZarrVis {__version__}")
    return parser.parse_args(argv)


def _resolve_root(path_arg: str | None, root_arg: Path | None) -> Path:
    if root_arg is not None:
        return root_arg.expanduser().resolve()
    if path_arg is not None and not _looks_remote(path_arg):
        p = Path(path_arg).expanduser().resolve()
        return p.parent
    return Path.home()


def _looks_remote(value: str) -> bool:
    return "://" in value


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.path and _looks_remote(args.path) and not args.allow_remote:
        print(
            "error: remote paths require --allow-remote (e.g. s3://, gs://, https://)",
            file=sys.stderr,
        )
        return 2

    root = _resolve_root(args.path, args.root)
    token = secrets.token_urlsafe(24)
    port = _resolve_port(args.host, args.port)

    # Lazy import so `--version` stays fast.
    import uvicorn

    from zarrvis.app import create_app

    app = create_app(
        root=root,
        token=token,
        initial_path=args.path,
        allow_remote=args.allow_remote,
    )

    # If port=0 we don't know the port until uvicorn binds; fall back to a
    # one-shot socket probe to pick a stable port to report.
    if port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((args.host, 0))
            port = s.getsockname()[1]

    url = _build_url(args.host, port, token)
    banner = [
        "",
        "  ZarrVis " + __version__,
        "  ──────────────────────────────────────────────",
        f"  root     : {root}",
        f"  remote   : {'enabled' if args.allow_remote else 'disabled'}",
        f"  url      : {url}",
        "  (Ctrl-C to stop)",
        "",
    ]
    print("\n".join(banner), flush=True)

    if not args.no_browser:
        _open_browser_soon(url)

    uvicorn.run(
        app,
        host=args.host,
        port=port,
        log_level="debug" if args.verbose else "info",
        access_log=args.verbose,
    )
    return 0
