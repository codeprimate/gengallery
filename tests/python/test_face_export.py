"""Tests for face export merge (Option B: faces[] on export image metadata)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from gengallery.constants import EXPORT_IMAGE_FACES_FIELD, GALLERIES_METADATA_DIR
from gengallery.services.face_processor import (
    detection_to_export_faces,
    export_faces_to_image_metadata,
)


def test_detection_to_export_faces_empty_when_no_detection() -> None:
    assert detection_to_export_faces(None) == []


def test_detection_to_export_faces_maps_assignment_fields() -> None:
    det = {
        "faces": [
            {
                "face_index": 0,
                "face_id": "abc123",
                "identity_id": "alice",
                "provenance": "propagated",
                "match_score": 0.91,
                "bbox": [0.1, 0.2, 0.3, 0.4],
            }
        ]
    }
    assert detection_to_export_faces(det) == [
        {
            "face_index": 0,
            "face_id": "abc123",
            "identity_id": "alice",
            "provenance": "propagated",
            "bbox": [0.1, 0.2, 0.3, 0.4],
        }
    ]


def test_export_faces_to_image_metadata_writes_faces_array(
    tmp_path: Path, monkeypatch
) -> None:
    output = tmp_path / "export" / "metadata" / "example"
    output.mkdir(parents=True)
    image_meta_path = output / "img001.json"
    image_meta_path.write_text(json.dumps({"id": "img001", "filename": "photo.jpg"}))

    galleries = tmp_path / "galleries" / GALLERIES_METADATA_DIR
    det_path = galleries / "detections" / "example" / "img001.json"
    det_path.parent.mkdir(parents=True)
    det_path.write_text(
        json.dumps(
            {
                "gallery_id": "example",
                "image_id": "img001",
                "source_filename": "photo.jpg",
                "faces": [
                    {
                        "face_index": 0,
                        "face_id": "face001",
                        "identity_id": "id_unnamed_abcd",
                        "provenance": "cluster",
                        "bbox": [0.0, 0.0, 0.5, 0.5],
                    }
                ],
            }
        )
    )

    config = {
        "source_path": str(tmp_path / "galleries"),
        "output_path": str(tmp_path / "export"),
    }
    from gengallery.services import image_processor as ip

    ip.apply_runtime_config(config)
    monkeypatch.chdir(tmp_path)

    all_detections = {
        "example:img001": json.loads(det_path.read_text()),
    }
    export_faces_to_image_metadata([("example", "img001", "")], all_detections)

    updated = json.loads(image_meta_path.read_text())
    assert EXPORT_IMAGE_FACES_FIELD in updated
    assert updated[EXPORT_IMAGE_FACES_FIELD] == [
        {
            "face_index": 0,
            "face_id": "face001",
            "identity_id": "id_unnamed_abcd",
            "provenance": "cluster",
            "bbox": [0.0, 0.0, 0.5, 0.5],
        }
    ]


def test_export_faces_to_image_metadata_writes_empty_array_when_no_faces(
    tmp_path: Path, monkeypatch
) -> None:
    output = tmp_path / "export" / "metadata" / "example"
    output.mkdir(parents=True)
    image_meta_path = output / "img001.json"
    image_meta_path.write_text(json.dumps({"id": "img001"}))

    config = {
        "source_path": str(tmp_path / "galleries"),
        "output_path": str(tmp_path / "export"),
    }
    from gengallery.services import image_processor as ip

    ip.apply_runtime_config(config)
    monkeypatch.chdir(tmp_path)

    export_faces_to_image_metadata([("example", "img001", "")], {})

    updated = json.loads(image_meta_path.read_text())
    assert updated[EXPORT_IMAGE_FACES_FIELD] == []


def test_sync_tags_to_export_metadata_copies_sidecar_tags(
    tmp_path: Path, monkeypatch
) -> None:
    source_gallery = tmp_path / "galleries" / "example"
    source_gallery.mkdir(parents=True)
    (source_gallery / "photo.jpg").write_bytes(b"fake")
    (source_gallery / "photo.yaml").write_text(
        yaml.dump({"tags": ["vacation", "person:alice"]})
    )

    output = tmp_path / "export" / "metadata" / "example"
    output.mkdir(parents=True)
    image_meta_path = output / "img001.json"
    image_meta_path.write_text(json.dumps({"id": "img001", "tags": []}))

    config = {
        "source_path": str(tmp_path / "galleries"),
        "output_path": str(tmp_path / "export"),
    }
    from gengallery.services import image_processor as ip
    from gengallery.services.face_processor import _sync_tags_to_export_metadata

    ip.apply_runtime_config(config)
    monkeypatch.chdir(tmp_path)

    all_detections = {
        "example:img001": {
            "gallery_id": "example",
            "image_id": "img001",
            "source_filename": "photo.jpg",
            "faces": [],
        }
    }
    _sync_tags_to_export_metadata(all_detections)

    updated = json.loads(image_meta_path.read_text())
    assert updated["tags"] == ["vacation", "person:alice"]
