"""Serve generated static site from ``output_path/public_html``."""

from __future__ import annotations

import contextlib
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from gengallery.constants import PUBLIC_HTML_SEGMENT


def resolve_serve_directory(project_root: Path, config: dict) -> Path:
    """Return resolved ``project_root / output_path / public_html``."""
    output_path = config["output_path"]
    return (project_root / Path(output_path) / PUBLIC_HTML_SEGMENT).resolve()


def run_serve(serve_dir: Path, *, host: str, port: int) -> None:
    """
    Bind an HTTP server to ``host:port`` serving files from ``serve_dir`` (no process chdir).

    Raises:
        SystemExit: 130 on keyboard interrupt (parity with interactive server scripts).
    """
    handler_cls = partial(SimpleHTTPRequestHandler, directory=str(serve_dir))
    httpd = HTTPServer((host, port), handler_cls)
    print(f"Serving on http://{host}:{port}/ from {serve_dir}")
    print("Press CTRL+C to stop the server")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        raise SystemExit(130) from None
    finally:
        with contextlib.suppress(Exception):
            httpd.server_close()
