"""Shared Rich progress layout for pipeline file-processing stages."""

from __future__ import annotations

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from gengallery.constants import (
    PROGRESS_ELLIPSIS,
    PROGRESS_FILENAME_MAX_LENGTH,
)


def truncate_middle(text: str, max_length: int) -> str:
    """Truncate *text* from the middle when it exceeds *max_length*."""
    if max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text
    if max_length <= len(PROGRESS_ELLIPSIS):
        return text[:max_length]
    keep = max_length - len(PROGRESS_ELLIPSIS)
    head = keep // 2
    tail = keep - head
    return f"{text[:head]}{PROGRESS_ELLIPSIS}{text[-tail:]}"


def format_file_task_description(stage_label: str, gallery_id: str, filename: str) -> str:
    """Build the live description for a file-processing progress task."""
    truncated = truncate_middle(filename, PROGRESS_FILENAME_MAX_LENGTH)
    return f"[cyan]{stage_label}[/] [blue]{gallery_id}[/]:{truncated}"


def format_phase_task_description(stage_label: str) -> str:
    """Build the description for a non-file pipeline phase."""
    return f"[cyan]{stage_label}[/] …"


def create_file_progress(console: Console | None = None, *, expand: bool = True) -> Progress:
    """Return a configured Rich Progress instance for pipeline stages."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        MofNCompleteColumn(),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console or Console(),
        expand=expand,
    )


def set_file_task_description(
    progress: Progress,
    task_id: int,
    stage_label: str,
    gallery_id: str,
    filename: str,
) -> None:
    """Update a progress task to show the current gallery and file."""
    progress.update(
        task_id,
        description=format_file_task_description(stage_label, gallery_id, filename),
    )


def set_phase_task_description(
    progress: Progress,
    task_id: int,
    stage_label: str,
) -> None:
    """Update a progress task to show a non-file pipeline phase."""
    progress.update(task_id, description=format_phase_task_description(stage_label))


__all__ = [
    "create_file_progress",
    "format_file_task_description",
    "format_phase_task_description",
    "set_file_task_description",
    "set_phase_task_description",
    "truncate_middle",
]
