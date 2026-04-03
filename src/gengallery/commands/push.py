"""gengallery push ssh — deploy via rsync + SSH."""

from __future__ import annotations

import argparse
from pathlib import Path

from gengallery.constants import EXIT_SUCCESS
from gengallery.pathing import load_project_config
from gengallery.services.deploy_ssh import run_deploy


def run(project_root: Path, args: argparse.Namespace) -> int:
    """Deploy after CLI validation (ssh block + local export tree)."""
    _ = args
    config = load_project_config(project_root)
    run_deploy(project_root, config)
    return EXIT_SUCCESS
