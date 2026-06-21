"""Tests for source gallery path helpers."""

from __future__ import annotations

from gengallery.services.gallery_paths import is_source_gallery_dirname


def test_is_source_gallery_dirname_rejects_metadata_dir() -> None:
    assert is_source_gallery_dirname("_metadata") is False


def test_is_source_gallery_dirname_rejects_underscore_prefix() -> None:
    assert is_source_gallery_dirname("_scratch") is False


def test_is_source_gallery_dirname_accepts_gallery_ids() -> None:
    assert is_source_gallery_dirname("20240715") is True
    assert is_source_gallery_dirname("example") is True
