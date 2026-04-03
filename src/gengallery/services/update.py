"""Orchestrates the full gallery refresh pipeline (image → video → gallery → site)."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from gengallery.services import gallery_processor, generator, image_processor, video_processor
from gengallery.services.image_processor import apply_runtime_config
from gengallery.services.pipeline_types import (
    GalleryIndexResult,
    ImageStageResult,
    OutputPath,
    SiteBuildResult,
    VideoStageResult,
)

_CONSOLE = Console()

_STAGE_TOTAL = 4


@contextmanager
def _chdir_project(project_root: Path):
    previous = Path.cwd()
    os.chdir(project_root)
    try:
        yield
    finally:
        os.chdir(previous)


# ── Rendering helpers ────────────────────────────────────────────────────────


def _fmt_elapsed(seconds: float) -> str:
    return f"[dim]{seconds:.2f}s[/dim]"


def _print_stage_header(n: int, label: str, gallery_counts: dict[str, int], unit: str) -> None:
    """Print the [N/4] label line and the discovery summary line."""
    _CONSOLE.print(f"\n  [bold]\\[{n}/{_STAGE_TOTAL}][/bold]  [cyan]{label}[/cyan]")
    if not gallery_counts:
        _CONSOLE.print(f"         [dim]No {unit}s found[/dim]")
        return
    chips = "     ".join(
        f"[blue]{gid}[/blue] [green]·[/green] [green]{count}[/green]"
        for gid, count in gallery_counts.items()
    )
    total = sum(gallery_counts.values())
    n_galleries = len(gallery_counts)
    gallery_word = "gallery" if n_galleries == 1 else "galleries"
    unit_word = f"{unit}s"
    _CONSOLE.print(f"         {chips}     [dim]→ {total} {unit_word}, {n_galleries} {gallery_word}[/dim]")


def _print_stage_completion(
    result: ImageStageResult | VideoStageResult,
) -> None:
    """Print a single completion line after the progress bars finish."""
    parts: list[str] = []
    if result.processed:
        parts.append(f"[green]{result.processed}[/green] processed")
    if result.skipped:
        parts.append(f"[dim]{result.skipped} up-to-date[/dim]")
    if result.failed:
        parts.append(f"[red]{result.failed} failed[/red]")
    parts.append(_fmt_elapsed(result.elapsed))
    _CONSOLE.print("         " + "  [dim]·[/dim]  ".join(parts))
    for filename, msg in result.errors:
        _CONSOLE.print(f"         [red]✗[/red] {filename} — {msg}")


def _print_gallery_index_result(result: GalleryIndexResult) -> None:
    """Print the checkmark list of indexed galleries and a summary line."""
    if result.indexed:
        chips = "  ".join(f"[green]✓[/green] [blue]{gid}[/blue]" for gid in result.indexed)
        _CONSOLE.print(f"         {chips}")
    if result.failed:
        for gid in result.failed:
            _CONSOLE.print(f"         [red]✗[/red] {gid}")
    parts = [f"[green]{len(result.indexed)}[/green] indexed"]
    if result.failed:
        parts.append(f"[red]{len(result.failed)} failed[/red]")
    parts.append(_fmt_elapsed(result.elapsed))
    _CONSOLE.print("         " + "  [dim]·[/dim]  ".join(parts))


def _print_site_build_result(result: SiteBuildResult) -> None:
    """Print tags, gallery chips, assets and timing for the site build stage."""
    if result.tags:
        tag_str = "  [dim]·[/dim]  ".join(
            f"[blue]{tag}[/blue] ({count})" for tag, count in result.tags.items()
        )
        _CONSOLE.print(f"         [dim]Tags[/dim]       {tag_str}")

    if result.galleries:
        gallery_chips: list[str] = []
        for g in result.galleries:
            flags = ""
            if g['is_featured']:
                flags += " ⭐"
            if g['is_encrypted']:
                flags += " 🔒"
            img_part = f"{g['image_count']} img" if g['image_count'] else ""
            vid_part = f"{g['video_count']} vid" if g['video_count'] else ""
            media = "  ·  ".join(x for x in (img_part, vid_part) if x)
            chip = f"[blue]{g['title']}[/blue]{flags}"
            if media:
                chip += f" [dim]({media})[/dim]"
            gallery_chips.append(chip)

        prefix = "         [dim]Galleries[/dim]  "
        indent = "         " + " " * 10
        line: list[str] = []
        line_len = 0
        first_line = True
        for chip in gallery_chips:
            # Rough width: strip markup for length estimate
            raw = Text.from_markup(chip).plain
            if line_len and line_len + len(raw) + 5 > 72:
                joiner = "  [dim]·[/dim]  "
                row = joiner.join(line)
                if first_line:
                    _CONSOLE.print(f"{prefix}{row}")
                    first_line = False
                else:
                    _CONSOLE.print(f"{indent}{row}")
                line = [chip]
                line_len = len(raw)
            else:
                line.append(chip)
                line_len += len(raw) + 5
        if line:
            row = "  [dim]·[/dim]  ".join(line)
            if first_line:
                _CONSOLE.print(f"{prefix}{row}")
            else:
                _CONSOLE.print(f"{indent}{row}")

    if result.assets_copied:
        asset_str = "  [dim]·[/dim]  ".join(result.assets_copied)
        _CONSOLE.print(f"         [dim]Assets[/dim]     {asset_str}")

    for err in result.errors:
        _CONSOLE.print(f"         [red]✗[/red] {err['stage']}: {err['error']}")

    _CONSOLE.print(f"         {_fmt_elapsed(result.elapsed)}")


def _print_output_table(output_paths: list[OutputPath]) -> None:
    """Render the output directory summary table."""
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Output", style="cyan", min_width=12)
    table.add_column("Path", style="yellow")
    table.add_column("Files", style="blue", justify="right")
    table.add_column("Size", style="magenta", justify="right")

    for op in output_paths:
        size_mb = op.size_bytes / (1024 * 1024)
        table.add_row(
            op.label,
            op.path,
            f"{op.file_count:,}",
            f"{size_mb:.1f} MB",
        )

    _CONSOLE.print()
    _CONSOLE.print(table)


# ── Pipeline ─────────────────────────────────────────────────────────────────


def run_update(project_root: Path, config: dict) -> None:
    """
    Run the full refresh pipeline in four stages:
    1. Image processing
    2. Video processing
    3. Gallery index generation
    4. Static site build

    The orchestrator owns all console output; individual stage ``run()``
    functions produce only Rich progress bars.
    """
    try:
        apply_runtime_config(config)
        pipeline_start = time.time()

        _CONSOLE.print()
        _CONSOLE.print(Rule("Refresh Galleries", style="bold cyan"))

        with _chdir_project(project_root):

            # ── Stage 1: Images ───────────────────────────────────────────
            image_counts = image_processor.discover_galleries()
            _print_stage_header(1, "Images", image_counts, unit="image")
            img_result = image_processor.run(list(image_counts))
            _print_stage_completion(img_result)

            # ── Stage 2: Videos ───────────────────────────────────────────
            video_counts = video_processor.discover_gallery_videos()
            _print_stage_header(2, "Videos", video_counts, unit="video")
            vid_result = video_processor.run(list(video_counts))
            _print_stage_completion(vid_result)

            # ── Stage 3: Gallery Index ────────────────────────────────────
            _CONSOLE.print(f"\n  [bold]\\[3/{_STAGE_TOTAL}][/bold]  [cyan]Gallery Index[/cyan]")
            idx_result = gallery_processor.run()
            _print_gallery_index_result(idx_result)

            # ── Stage 4: Site Build ───────────────────────────────────────
            _CONSOLE.print(f"\n  [bold]\\[4/{_STAGE_TOTAL}][/bold]  [cyan]Site Build[/cyan]")
            site_result = generator.run()
            _print_site_build_result(site_result)

        # ── Final summary ─────────────────────────────────────────────────
        _CONSOLE.print()
        _CONSOLE.print(Rule(style="dim"))

        _print_output_table(site_result.output_paths)

        total_images = sum(image_counts.values())
        total_videos = sum(video_counts.values())
        total_galleries = len(idx_result.indexed)
        elapsed = time.time() - pipeline_start

        _CONSOLE.print(
            f"\n  [bold green]✨ Refresh complete[/bold green]"
            f"  [dim]·[/dim]  [green]{total_galleries}[/green] galleries"
            f"  [dim]·[/dim]  [green]{total_images}[/green] images"
            f"  [dim]·[/dim]  [green]{total_videos}[/green] videos"
            f"  [dim]·[/dim]  {_fmt_elapsed(elapsed)}"
        )

    except KeyboardInterrupt:
        _CONSOLE.print("\n[yellow]Gallery Refresh interrupted by user[/yellow]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as e:
        _CONSOLE.print(f"\n[red]Gallery Refresh failed: {e!s}[/red]")
        raise SystemExit(1) from e
