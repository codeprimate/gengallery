"""Tests for gallery_processor interaction with face metadata."""

from __future__ import annotations

import json
from pathlib import Path

from gengallery.constants import FACES_DETECTIONS_DIR, FACES_META_DIR
from gengallery.services import gallery_processor, image_processor


def test_run_preserves_face_metadata_directory(tmp_path: Path, monkeypatch) -> None:
    """Gallery index cleanup must not delete export/metadata/faces/."""
    source = tmp_path / "galleries" / "example"
    source.mkdir(parents=True)
    (source / "gallery.yaml").write_text(
        "title: Example\ndate: 2026-01-01\nlocation: ''\ndescription: ''\n"
        "tags: []\ncontent: ''\nencrypted: false\n"
    )
    (source / "photo.jpg").write_bytes(b"fake")

    output = tmp_path / "export"
    meta_gallery = output / "metadata" / "example"
    meta_gallery.mkdir(parents=True)
    (meta_gallery / "abc123.json").write_text(
        json.dumps(
            {
                "id": "abc123",
                "filename": "photo.jpg",
                "media_type": "image",
                "path": "/galleries/example/full/abc123.jpg",
                "thumbnail_path": "/galleries/example/thumbnail/abc123.jpg",
                "cover_path": "/galleries/example/cover/abc123.jpg",
                "exif": {},
            }
        )
    )

    face_det = (
        output
        / "metadata"
        / FACES_META_DIR
        / FACES_DETECTIONS_DIR
        / "example"
        / "abc123.json"
    )
    face_det.parent.mkdir(parents=True)
    face_det.write_text(json.dumps({"gallery_id": "example", "image_id": "abc123", "faces": []}))

    config = {
        "source_path": str(tmp_path / "galleries"),
        "output_path": str(output),
        "image_sizes": {"thumbnail": 450, "cover": 1024, "full": 3840},
    }
    image_processor.apply_runtime_config(config)
    monkeypatch.chdir(tmp_path)

    result = gallery_processor.run()

    assert "example" in result.indexed
    assert FACES_META_DIR not in result.removed
    assert face_det.exists()
