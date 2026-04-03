"""gengallery init: create project directory if needed, then materialize packaged scaffold."""

from __future__ import annotations

import argparse
from pathlib import Path

from gengallery.services.init_scaffold import run_init


def run(project_root: Path, args: argparse.Namespace) -> int:
    """Create missing project directory, then unpack scaffold (strict conflict policy)."""
    _ = args
    target = project_root
    if not target.exists():
        target.mkdir(parents=True, exist_ok=False)
    return run_init(target)
