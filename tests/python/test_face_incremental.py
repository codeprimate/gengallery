"""Tests for face detection incremental skip behavior."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from gengallery.constants import CONFIG_FILENAME, FACES_DETECTIONS_DIR, GALLERIES_METADATA_DIR
from gengallery.services import image_processor as ip
from gengallery.services.face_processor import (
    _detection_is_fresh,
    _detection_path,
    run,
)


def _write_min_project(project: Path) -> tuple[str, str, str]:
    """Create a minimal gallery project and return (gallery_id, filename, image_id)."""
    gallery_id = "example"
    filename = "photo.jpg"
    image_id = hashlib.md5(f"{gallery_id}:{filename}".encode()).hexdigest()[:12]

    gallery_dir = project / "galleries" / gallery_id
    gallery_dir.mkdir(parents=True)
    (gallery_dir / "gallery.yaml").write_text(
        "title: Example\ndate: 2026-01-01\nlocation: ''\ndescription: ''\n"
        "tags: []\ncontent: ''\nencrypted: false\n"
    )
    (gallery_dir / filename).write_bytes(b"fake-image-data")
    (project / CONFIG_FILENAME).write_text(
        yaml.dump(
            {
                "source_path": "./galleries",
                "output_path": "./export",
                "image_sizes": {"thumbnail": 450},
                "jpg_quality": 85,
            }
        )
    )
    return gallery_id, filename, image_id


def test_detection_is_fresh_when_cache_is_newer_than_image(
    tmp_path: Path, monkeypatch
) -> None:
    gallery_id, filename, image_id = _write_min_project(tmp_path)
    config = yaml.safe_load((tmp_path / CONFIG_FILENAME).read_text())
    ip.apply_runtime_config(config)
    monkeypatch.chdir(tmp_path)

    det_path = _detection_path(gallery_id, image_id)
    det_path.parent.mkdir(parents=True)
    det_path.write_text(
        json.dumps(
            {
                "gallery_id": gallery_id,
                "image_id": image_id,
                "source_filename": filename,
                "faces": [],
            }
        )
    )
    time.sleep(0.02)
    os.utime(det_path, None)

    image_path = tmp_path / "galleries" / gallery_id / filename
    face_cfg: dict = config.get("faces", {})

    assert _detection_is_fresh(
        gallery_id,
        image_id,
        os.path.getmtime(image_path),
        face_cfg,
    )


def test_detection_stays_fresh_after_config_yaml_is_touched(
    tmp_path: Path, monkeypatch
) -> None:
    """Editing config.yaml must not force re-detection when the image is unchanged."""
    gallery_id, filename, image_id = _write_min_project(tmp_path)
    config = yaml.safe_load((tmp_path / CONFIG_FILENAME).read_text())
    ip.apply_runtime_config(config)
    monkeypatch.chdir(tmp_path)

    det_path = _detection_path(gallery_id, image_id)
    det_path.parent.mkdir(parents=True)
    det_path.write_text(
        json.dumps(
            {
                "gallery_id": gallery_id,
                "image_id": image_id,
                "source_filename": filename,
                "faces": [],
            }
        )
    )
    time.sleep(0.02)
    os.utime(det_path, None)

    config_path = tmp_path / CONFIG_FILENAME
    config_path.write_text(config_path.read_text() + "# touched\n")

    image_path = tmp_path / "galleries" / gallery_id / filename
    face_cfg: dict = config.get("faces", {})

    assert _detection_is_fresh(
        gallery_id,
        image_id,
        os.path.getmtime(image_path),
        face_cfg,
    )


def test_detection_stays_fresh_after_identities_yaml_is_touched(
    tmp_path: Path, monkeypatch
) -> None:
    """faces assign updates identities.yaml; detection cache must remain valid."""
    gallery_id, filename, image_id = _write_min_project(tmp_path)
    config = yaml.safe_load((tmp_path / CONFIG_FILENAME).read_text())
    ip.apply_runtime_config(config)
    monkeypatch.chdir(tmp_path)

    det_path = _detection_path(gallery_id, image_id)
    det_path.parent.mkdir(parents=True)
    det_path.write_text(
        json.dumps(
            {
                "gallery_id": gallery_id,
                "image_id": image_id,
                "source_filename": filename,
                "faces": [],
            }
        )
    )
    time.sleep(0.02)
    os.utime(det_path, None)

    identities_path = tmp_path / "galleries" / "identities.yaml"
    identities_path.write_text(
        yaml.dump(
            {
                "identities": {
                    "alice": {
                        "display_name": "Alice",
                        "positives": [
                            {"gallery": gallery_id, "image": filename, "face": 0}
                        ],
                    }
                }
            }
        )
    )

    image_path = tmp_path / "galleries" / gallery_id / filename
    face_cfg: dict = config.get("faces", {})

    assert _detection_is_fresh(
        gallery_id,
        image_id,
        os.path.getmtime(image_path),
        face_cfg,
    )


def test_run_skips_detection_when_cache_is_fresh(tmp_path: Path, monkeypatch) -> None:
    gallery_id, filename, image_id = _write_min_project(tmp_path)
    det_path = (
        tmp_path
        / "galleries"
        / GALLERIES_METADATA_DIR
        / FACES_DETECTIONS_DIR
        / gallery_id
        / f"{image_id}.json"
    )
    det_path.parent.mkdir(parents=True)
    det_path.write_text(
        json.dumps(
            {
                "gallery_id": gallery_id,
                "image_id": image_id,
                "source_filename": filename,
                "faces": [],
            }
        )
    )
    time.sleep(0.02)
    os.utime(det_path, None)

    ip.apply_runtime_config(yaml.safe_load((tmp_path / CONFIG_FILENAME).read_text()))
    monkeypatch.chdir(tmp_path)

    mock_analyzer = MagicMock()
    monkeypatch.setattr(
        "gengallery.services.face_processor.get_face_analyzer",
        lambda: mock_analyzer,
    )
    monkeypatch.setattr(
        "gengallery.services.face_processor.analyze_image",
        MagicMock(side_effect=AssertionError("analyze_image should not run")),
    )

    result = run()

    assert result.images_skipped == 1
    assert result.images_processed == 0
    mock_analyzer.assert_not_called()
