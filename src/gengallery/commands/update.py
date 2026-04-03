"""gengallery update — full refresh pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from gengallery.constants import EXIT_SUCCESS
from gengallery.pathing import load_project_config
from gengallery.services.update import run_update


def run(project_root: Path, args: argparse.Namespace) -> int:
    """Run build pipeline after CLI validation (config + source dir)."""
    _ = args
    config = load_project_config(project_root)
    run_update(project_root, config)
    return EXIT_SUCCESS
