"""Dataclasses for structured results returned by each pipeline stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageStageResult:
    gallery_counts: dict[str, int]
    total: int
    processed: int
    skipped: int
    failed: int
    elapsed: float
    errors: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class VideoStageResult:
    gallery_counts: dict[str, int]
    total: int
    processed: int
    skipped: int
    failed: int
    elapsed: float
    errors: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class GalleryIndexResult:
    indexed: list[str]
    removed: list[str]
    failed: list[str]
    elapsed: float


@dataclass
class OutputPath:
    label: str
    path: str
    file_count: int
    size_bytes: int


@dataclass
class SiteBuildResult:
    galleries: list[dict]
    tags: dict[str, int]
    assets_copied: list[str]
    output_paths: list[OutputPath]
    errors: list[dict]
    elapsed: float


@dataclass
class FaceStageResult:
    images_processed: int
    images_skipped: int
    faces_detected: int
    identities_named: int
    clusters_anonymous: int
    elapsed: float
    errors: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Extra info surfaced in the pipeline summary
    extra: dict[str, Any] = field(default_factory=dict)
