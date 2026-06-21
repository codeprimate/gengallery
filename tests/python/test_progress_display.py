"""Tests for shared pipeline progress display helpers."""

from gengallery.constants import PROGRESS_ELLIPSIS, PROGRESS_FILENAME_MAX_LENGTH
from gengallery.services.progress_display import (
    format_file_task_description,
    format_phase_task_description,
    truncate_middle,
)


def test_truncate_middle_leaves_short_text_unchanged() -> None:
    assert truncate_middle("party.jpg", PROGRESS_FILENAME_MAX_LENGTH) == "party.jpg"


def test_truncate_middle_shortens_long_text_from_center() -> None:
    name = "IMG_20240715_very_long_vacation_filename_party.jpg"
    truncated = truncate_middle(name, 20)
    assert len(truncated) == 20
    assert PROGRESS_ELLIPSIS in truncated
    assert truncated.startswith("IMG_2024")
    assert truncated.endswith("party.jpg")


def test_format_file_task_description_includes_gallery_and_filename() -> None:
    description = format_file_task_description("Face Detection", "20240715", "party.jpg")
    assert "Face Detection" in description
    assert "20240715" in description
    assert "party.jpg" in description


def test_format_phase_task_description_uses_phase_label() -> None:
    assert format_phase_task_description("Clustering faces") == "[cyan]Clustering faces[/] …"
