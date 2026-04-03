"""Dataclasses for structured results returned by each pipeline stage."""

from __future__ import annotations

from dataclasses import dataclass, field


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
