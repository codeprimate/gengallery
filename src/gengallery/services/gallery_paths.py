"""Shared helpers for source gallery directory layout."""

from __future__ import annotations

from gengallery.constants import GALLERIES_METADATA_DIR


def is_source_gallery_dirname(name: str) -> bool:
    """Return True when *name* is a gallery folder under ``source_path``."""
    if name == GALLERIES_METADATA_DIR:
        return False
    return not name.startswith("_")
