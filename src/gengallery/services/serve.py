"""Serve generated static site from ``output_path/public_html``."""

from __future__ import annotations

import contextlib
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from gengallery.constants import PUBLIC_HTML_SEGMENT
from gengallery.services.urls import normalize_base_path, translate_request_path


class _PrefixedHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Strips a configured URL prefix from requests before filesystem lookup.

    Sibling of :class:`SimpleHTTPRequestHandler` — when *base_path* is set, this
    handler translates ``/gallery/css/tailwind.css`` → ``/css/tailwind.css`` so the
    local dev server serves files from ``public_html/`` even though the HTML
    references them under the prefix.
    """

    def __init__(self, *args, base_path="", directory=None, **kwargs):
        self.base_path = normalize_base_path(base_path)
        super().__init__(*args, directory=directory, **kwargs)

    def translate_path(self, path):
        return super().translate_path(translate_request_path(path, self.base_path))


def resolve_serve_directory(project_root: Path, config: dict) -> Path:
    """Return resolved ``project_root / output_path / public_html``."""
    output_path = config["output_path"]
    return (project_root / Path(output_path) / PUBLIC_HTML_SEGMENT).resolve()


def run_serve(serve_dir: Path, *, host: str, port: int, base_path: str = "") -> None:
    """
    Bind an HTTP server to ``host:port`` serving files from ``serve_dir``.

    When *base_path* is non-empty, the server translates incoming prefixed requests
    transparently (see :class:`_PrefixedHTTPRequestHandler`) and the printed URL
    includes the prefix so the operator can click directly.
    """
    normalized = normalize_base_path(base_path)
    if normalized:
        handler_cls = partial(
            _PrefixedHTTPRequestHandler,
            directory=str(serve_dir),
            base_path=normalized,
        )
    else:
        handler_cls = partial(SimpleHTTPRequestHandler, directory=str(serve_dir))

    httpd = HTTPServer((host, port), handler_cls)
    url = f"http://{host}:{port}{normalized}/" if normalized else f"http://{host}:{port}/"
    print(f"Serving on {url} from {serve_dir}")
    print("Press CTRL+C to stop the server")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        raise SystemExit(130) from None
    finally:
        with contextlib.suppress(Exception):
            httpd.server_close()
