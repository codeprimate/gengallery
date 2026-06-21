"""Tests for update pipeline orchestration (stage order and wiring)."""

from __future__ import annotations

from pathlib import Path

from gengallery.services.pipeline_types import (
    FaceStageResult,
    GalleryIndexResult,
    ImageStageResult,
    OutputPath,
    SiteBuildResult,
    VideoStageResult,
)
from gengallery.services.update import run_update

# ---------------------------------------------------------------------------
# Minimal stub results
# ---------------------------------------------------------------------------

_IMG_RESULT = ImageStageResult(
    gallery_counts={}, total=0, processed=0, skipped=0, failed=0, elapsed=0.0
)
_FACE_RESULT = FaceStageResult(
    images_processed=0,
    images_skipped=0,
    faces_detected=0,
    identities_named=0,
    clusters_anonymous=0,
    elapsed=0.0,
)
_VID_RESULT = VideoStageResult(
    gallery_counts={}, total=0, processed=0, skipped=0, failed=0, elapsed=0.0
)
_IDX_RESULT = GalleryIndexResult(indexed=[], removed=[], failed=[], elapsed=0.0)
_SITE_RESULT = SiteBuildResult(
    galleries=[],
    tags={},
    assets_copied=[],
    output_paths=[OutputPath(label="export", path="export", file_count=0, size_bytes=0)],
    errors=[],
    elapsed=0.0,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_update_invokes_stages_in_order(monkeypatch, tmp_path: Path) -> None:
    """Pipeline runs image → faces → video → gallery_index → site_build in that order."""
    calls: list[str] = []

    monkeypatch.setattr(
        "gengallery.services.update.image_processor.discover_galleries",
        lambda: (calls.append("image_discover") or {}),
    )
    monkeypatch.setattr(
        "gengallery.services.update.image_processor.run",
        lambda _names: (calls.append("image") or _IMG_RESULT),
    )
    monkeypatch.setattr(
        "gengallery.services.update.face_processor.discover_galleries",
        lambda: (calls.append("face_discover") or {}),
    )
    monkeypatch.setattr(
        "gengallery.services.update.face_processor.run",
        lambda: (calls.append("faces") or _FACE_RESULT),
    )
    monkeypatch.setattr(
        "gengallery.services.update.video_processor.discover_gallery_videos",
        lambda: (calls.append("video_discover") or {}),
    )
    monkeypatch.setattr(
        "gengallery.services.update.video_processor.run",
        lambda _names: (calls.append("video") or _VID_RESULT),
    )
    monkeypatch.setattr(
        "gengallery.services.update.gallery_processor.run",
        lambda: (calls.append("gallery") or _IDX_RESULT),
    )
    monkeypatch.setattr(
        "gengallery.services.update.generator.run",
        lambda: (calls.append("generator") or _SITE_RESULT),
    )

    cfg = {"source_path": "./galleries", "output_path": "./export"}
    run_update(tmp_path, cfg)

    # Verify stage execution order (discovery + run interleaved per stage)
    assert calls == [
        "image_discover", "image",
        "face_discover", "faces",
        "video_discover", "video",
        "gallery",
        "generator",
    ]


def test_apply_runtime_config_populates_shared_config(tmp_path: Path, monkeypatch) -> None:
    """Shared config dict is filled before stages run (video reads image_processor.config)."""
    monkeypatch.setattr(
        "gengallery.services.update.image_processor.discover_galleries", lambda: {}
    )
    monkeypatch.setattr(
        "gengallery.services.update.image_processor.run", lambda _: _IMG_RESULT
    )
    monkeypatch.setattr(
        "gengallery.services.update.face_processor.discover_galleries", lambda: {}
    )
    monkeypatch.setattr(
        "gengallery.services.update.face_processor.run", lambda: _FACE_RESULT
    )
    monkeypatch.setattr(
        "gengallery.services.update.video_processor.discover_gallery_videos", lambda: {}
    )
    monkeypatch.setattr(
        "gengallery.services.update.video_processor.run", lambda _: _VID_RESULT
    )
    monkeypatch.setattr(
        "gengallery.services.update.gallery_processor.run", lambda: _IDX_RESULT
    )
    monkeypatch.setattr(
        "gengallery.services.update.generator.run", lambda: _SITE_RESULT
    )

    from gengallery.services import image_processor as ip

    cfg = {"source_path": "s", "output_path": "o", "site_name": "t"}
    run_update(tmp_path, cfg)
    assert ip.config.get("site_name") == "t"
    assert ip.config.get("source_path") == "s"
