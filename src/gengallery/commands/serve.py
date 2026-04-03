"""gengallery serve — static HTTP server for generated site."""

from __future__ import annotations

import argparse
from pathlib import Path

from gengallery.constants import (
    EXIT_SUCCESS,
    SERVE_BIND_HOST,
    SERVE_PORT_MAX,
    SERVE_PORT_MIN,
)
from gengallery.errors import CliUserError
from gengallery.pathing import load_project_config
from gengallery.services.serve import resolve_serve_directory, run_serve


def run(project_root: Path, args: argparse.Namespace) -> int:
    """Serve ``public_html`` after CLI validation (tree exists)."""
    port = int(args.port)
    if not (SERVE_PORT_MIN <= port <= SERVE_PORT_MAX):
        raise CliUserError(
            f"Port must be between {SERVE_PORT_MIN} and {SERVE_PORT_MAX}, got {port}.",
        )
    config = load_project_config(project_root)
    serve_dir = resolve_serve_directory(project_root, config)
    run_serve(serve_dir, host=SERVE_BIND_HOST, port=port)
    return EXIT_SUCCESS
