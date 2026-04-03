"""Orchestrates the full gallery refresh pipeline (image → video → gallery → site)."""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from gengallery.services import gallery_processor, generator, image_processor, video_processor
from gengallery.services.image_processor import apply_runtime_config

_CONSOLE = Console()


@contextmanager
def _chdir_project(project_root: Path):
    previous = Path.cwd()
    os.chdir(project_root)
    try:
        yield
    finally:
        os.chdir(previous)


def _run_stage_with_all_argv(module_main, argv0: str, saved_argv: list[str]) -> None:
    sys.argv[:] = [argv0, "--all"]
    try:
        module_main()
    finally:
        sys.argv[:] = saved_argv


def run_update(project_root: Path, config: dict) -> None:
    """
    Run stages in the same order as the historical monolithic refresh orchestrator.

    - Injects ``config`` into the shared in-process dict used by image/video/gallery services.
    - Sets the process working directory to ``project_root`` for path-relative I/O (templates,
      ``config.yaml`` reads in generator, etc.).
    - Passes ``--all`` to image and video stages via ``sys.argv`` (parity with refresh when no
      gallery is specified).
    """
    try:
        apply_runtime_config(config)
        title = Text("Refresh Galleries", style="bold cyan")
        _CONSOLE.print(Panel(title, border_style="cyan"))
        pipeline_start = time.time()
        argv0 = sys.argv[0] if sys.argv else "gengallery"
        saved_argv = sys.argv[:]

        with _chdir_project(project_root):
            t0 = time.time()
            _run_stage_with_all_argv(image_processor.main, argv0, saved_argv)
            _CONSOLE.print(f"[green]✓ Image processing completed in {time.time() - t0:.2f}s[/]")

            t0 = time.time()
            _run_stage_with_all_argv(video_processor.main, argv0, saved_argv)
            _CONSOLE.print(f"[green]✓ Video processing completed in {time.time() - t0:.2f}s[/]")

            t0 = time.time()
            gallery_processor.main()
            _CONSOLE.print(f"[green]✓ Gallery processing completed in {time.time() - t0:.2f}s[/]")

            t0 = time.time()
            generator.main()
            _CONSOLE.print(f"[green]✓ Site generation completed in {time.time() - t0:.2f}s[/]")

        _CONSOLE.print(
            "\n[bold green]✨ Gallery Refresh completed successfully in "
            f"{time.time() - pipeline_start:.2f}s![/]"
        )
    except KeyboardInterrupt:
        _CONSOLE.print("\n[yellow]Gallery Refresh interrupted by user[/]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as e:
        _CONSOLE.print(f"\n[red]Gallery Refresh failed: {e!s}[/]")
        raise SystemExit(1) from e
