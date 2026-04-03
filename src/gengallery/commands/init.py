"""gengallery init: create project directory if needed, then materialize packaged scaffold."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from gengallery import __version__
from gengallery.constants import (
    CLI_APP_NAME,
    CONFIG_FILENAME,
    EXIT_SUCCESS,
    GALLERIES_DIRNAME,
    PACKAGE_JSON_FILENAME,
    TEMPLATES_DIRNAME,
)
from gengallery.services.init_scaffold import run_init
from gengallery.services.npm_install import run_npm_install

_INIT_CONSOLE = Console()

INIT_MSG_LEAD_IN = "is creating a new project at"
INIT_MSG_CREATED_PROJECT_DIR = "Created project directory:"
INIT_MSG_WROTE_SCAFFOLD = "Wrote scaffold:"
INIT_MSG_NPM_INSTALLING = "Installing npm dependencies (this may take a moment)…"
INIT_MSG_NPM_INSTALLED = "Installed npm dependencies (Tailwind CSS)."
INIT_MSG_SUCCESS = "Init completed successfully."


def run(project_root: Path, args: argparse.Namespace) -> int:
    """Create missing project directory, then unpack scaffold (strict conflict policy)."""
    _ = args
    target = project_root
    banner_path = target.resolve()
    _INIT_CONSOLE.print(
        f"[bold cyan]{CLI_APP_NAME}[/] [dim](v{__version__})[/] {INIT_MSG_LEAD_IN} "
        f"[bold]{banner_path}[/]…"
    )
    created_project_dir = not target.exists()
    if created_project_dir:
        target.mkdir(parents=True, exist_ok=False)
    files_written = run_init(target)
    resolved = target.resolve()
    if created_project_dir:
        _INIT_CONSOLE.print(
            f"[green]✓[/green] {INIT_MSG_CREATED_PROJECT_DIR} [bold]{resolved}[/bold]"
        )
    _INIT_CONSOLE.print(
        f"[green]✓[/green] {INIT_MSG_WROTE_SCAFFOLD} [bold]{CONFIG_FILENAME}[/bold], "
        f"[bold]{PACKAGE_JSON_FILENAME}[/bold], [bold]{GALLERIES_DIRNAME}/[/bold], "
        f"[bold]{TEMPLATES_DIRNAME}/[/bold] ([bold]{files_written}[/bold] files)."
    )
    _INIT_CONSOLE.print(f"[yellow]→[/yellow] {INIT_MSG_NPM_INSTALLING}")
    run_npm_install(resolved)
    _INIT_CONSOLE.print(f"[green]✓[/green] {INIT_MSG_NPM_INSTALLED}")
    _INIT_CONSOLE.print(f"[bold green]{INIT_MSG_SUCCESS}[/bold green]")
    return EXIT_SUCCESS
