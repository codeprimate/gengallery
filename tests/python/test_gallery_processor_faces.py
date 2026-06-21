"""Tests for gallery_processor face metadata integration."""

from __future__ import annotations

import json
from pathlib import Path

from gengallery.constants import (
    EXPORT_GALLERY_IDENTITIES_FIELD,
    FACES_DETECTIONS_DIR,
    GALLERIES_METADATA_DIR,
)
from gengallery.services import gallery_processor, image_processor
from gengallery.services.gallery_processor import identities_from_items


def test_identities_from_items_includes_named_and_anonymous() -> None:
    items = [
        {
            "faces": [
                {"identity_id": "alice", "provenance": "positive"},
                {"identity_id": "id_unnamed_abcd", "provenance": "cluster"},
                {"identity_id": None, "provenance": "unassigned"},
            ]
        }
    ]
    assert identities_from_items(items) == ["alice", "id_unnamed_abcd"]


def test_process_gallery_adds_identities_rollup(tmp_path: Path, monkeypatch) -> None:
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
                "faces": [
                    {
                        "face_index": 0,
                        "face_id": "f1",
                        "identity_id": "alice",
                        "provenance": "positive",
                        "bbox": [0.1, 0.1, 0.2, 0.2],
                    }
                ],
            }
        )
    )

    config = {
        "source_path": str(tmp_path / "galleries"),
        "output_path": str(output),
        "image_sizes": {"thumbnail": 450, "cover": 1024, "full": 3840},
    }
    image_processor.apply_runtime_config(config)
    monkeypatch.chdir(tmp_path)

    gallery_data = gallery_processor.process_gallery(str(source))
    assert gallery_data[EXPORT_GALLERY_IDENTITIES_FIELD] == ["alice"]


def test_run_ignores_galleries_metadata_directory(tmp_path: Path, monkeypatch) -> None:
    """_metadata under source_path is not treated as a gallery."""
    source_root = tmp_path / "galleries"
    example = source_root / "example"
    example.mkdir(parents=True)
    (example / "gallery.yaml").write_text(
        "title: Example\ndate: 2026-01-01\nlocation: ''\ndescription: ''\n"
        "tags: []\ncontent: ''\nencrypted: false\n"
    )
    (example / "photo.jpg").write_bytes(b"fake")

    meta_gallery = tmp_path / "export" / "metadata" / "example"
    meta_gallery.mkdir(parents=True)
    (meta_gallery / "abc123.json").write_text(
        json.dumps(
            {
                "id": "abc123",
                "filename": "photo.jpg",
                "path": "/galleries/example/full/abc123.jpg",
                "thumbnail_path": "/galleries/example/thumbnail/abc123.jpg",
                "cover_path": "/galleries/example/cover/abc123.jpg",
                "exif": {},
                "faces": [],
            }
        )
    )

    face_meta = source_root / GALLERIES_METADATA_DIR / FACES_DETECTIONS_DIR / "example"
    face_meta.mkdir(parents=True)
    (face_meta / "abc123.json").write_text(json.dumps({"faces": []}))

    config = {
        "source_path": str(source_root),
        "output_path": str(tmp_path / "export"),
        "image_sizes": {"thumbnail": 450, "cover": 1024, "full": 3840},
    }
    image_processor.apply_runtime_config(config)
    monkeypatch.chdir(tmp_path)

    result = gallery_processor.run()

    assert result.indexed == ["example"]
    assert (source_root / GALLERIES_METADATA_DIR).exists()
