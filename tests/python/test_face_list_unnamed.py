"""Tests for anonymous identity listing."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from gengallery.constants import (
    CONFIG_FILENAME,
    FACE_PROVENANCE_CLUSTER,
    FACE_PROVENANCE_UNASSIGNED,
    FACE_UNASSIGNED_LIST_LABEL,
    FACES_DETECTIONS_DIR,
    GALLERIES_METADATA_DIR,
)
from gengallery.services.face_processor import (
    UnnamedIdentityGroup,
    list_unnamed_identity_groups,
    load_all_detections,
)


def _write_min_project(project: Path) -> None:
    gallery_dir = project / "galleries" / "20240715"
    gallery_dir.mkdir(parents=True)
    (gallery_dir / "gallery.yaml").write_text(
        "title: Party\ndate: 2024-07-15\nlocation: ''\ndescription: ''\n"
        "tags: []\ncontent: ''\nencrypted: false\n"
    )
    (gallery_dir / "party.jpg").write_bytes(b"fake")
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


def _write_detection(
    project: Path,
    *,
    gallery_id: str,
    image_id: str,
    source_filename: str,
    faces: list[dict],
) -> None:
    det_dir = (
        project
        / "galleries"
        / GALLERIES_METADATA_DIR
        / FACES_DETECTIONS_DIR
        / gallery_id
    )
    det_dir.mkdir(parents=True, exist_ok=True)
    (det_dir / f"{image_id}.json").write_text(
        json.dumps(
            {
                "gallery_id": gallery_id,
                "image_id": image_id,
                "source_filename": source_filename,
                "faces": faces,
            }
        )
    )


def test_list_unnamed_identity_groups_clusters_and_singletons(tmp_path: Path, monkeypatch) -> None:
    _write_min_project(tmp_path)
    _write_detection(
        tmp_path,
        gallery_id="20240715",
        image_id="img001",
        source_filename="party.jpg",
        faces=[
            {
                "face_index": 0,
                "detection_confidence": 0.95,
                "identity_id": "id_unnamed_abcd1234",
                "provenance": FACE_PROVENANCE_CLUSTER,
            },
            {
                "face_index": 1,
                "detection_confidence": 0.88,
                "identity_id": "id_unnamed_abcd1234",
                "provenance": FACE_PROVENANCE_CLUSTER,
            },
        ],
    )
    _write_detection(
        tmp_path,
        gallery_id="20240715",
        image_id="img002",
        source_filename="solo.jpg",
        faces=[
            {
                "face_index": 0,
                "detection_confidence": 0.91,
                "identity_id": None,
                "provenance": FACE_PROVENANCE_UNASSIGNED,
            },
        ],
    )

    monkeypatch.chdir(tmp_path)
    from gengallery.services import image_processor as ip

    ip.apply_runtime_config(yaml.safe_load((tmp_path / CONFIG_FILENAME).read_text()))

    groups = list_unnamed_identity_groups(load_all_detections())

    assert len(groups) == 2
    assert groups[0] == UnnamedIdentityGroup(
        "id_unnamed_abcd1234",
        groups[0].members,
    )
    assert groups[0].face_count == 2
    assert groups[0].sample_path == "20240715/party.jpg"
    assert groups[1].identity_id == FACE_UNASSIGNED_LIST_LABEL
    assert groups[1].face_count == 1
    assert groups[1].sample_path == "20240715/solo.jpg"


def test_list_unnamed_identity_groups_respects_filters(tmp_path: Path, monkeypatch) -> None:
    _write_min_project(tmp_path)
    gallery_dir = tmp_path / "galleries" / "20250801"
    gallery_dir.mkdir()
    (gallery_dir / "gallery.yaml").write_text(
        "title: Beach\ndate: 2025-08-01\nlocation: ''\ndescription: ''\n"
        "tags: []\ncontent: ''\nencrypted: false\n"
    )
    (gallery_dir / "beach.jpg").write_bytes(b"fake")

    _write_detection(
        tmp_path,
        gallery_id="20240715",
        image_id="img001",
        source_filename="party.jpg",
        faces=[
            {
                "face_index": 0,
                "detection_confidence": 0.95,
                "identity_id": "id_unnamed_abcd1234",
                "provenance": FACE_PROVENANCE_CLUSTER,
            },
        ],
    )
    _write_detection(
        tmp_path,
        gallery_id="20250801",
        image_id="img002",
        source_filename="beach.jpg",
        faces=[
            {
                "face_index": 0,
                "detection_confidence": 0.90,
                "identity_id": "id_unnamed_zzzz9999",
                "provenance": FACE_PROVENANCE_CLUSTER,
            },
            {
                "face_index": 1,
                "detection_confidence": 0.85,
                "identity_id": "id_unnamed_zzzz9999",
                "provenance": FACE_PROVENANCE_CLUSTER,
            },
        ],
    )

    monkeypatch.chdir(tmp_path)
    from gengallery.services import image_processor as ip

    ip.apply_runtime_config(yaml.safe_load((tmp_path / CONFIG_FILENAME).read_text()))
    all_detections = load_all_detections()

    by_gallery = list_unnamed_identity_groups(all_detections, gallery_id="20250801")
    assert len(by_gallery) == 1
    assert by_gallery[0].identity_id == "id_unnamed_zzzz9999"
    assert by_gallery[0].face_count == 2

    min_two = list_unnamed_identity_groups(all_detections, min_faces=2)
    assert [group.identity_id for group in min_two] == ["id_unnamed_zzzz9999"]

    no_singletons = list_unnamed_identity_groups(
        all_detections,
        include_singletons=False,
    )
    assert all(group.identity_id != FACE_UNASSIGNED_LIST_LABEL for group in no_singletons)


def test_run_list_unnamed_prints_table(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_min_project(tmp_path)
    _write_detection(
        tmp_path,
        gallery_id="20240715",
        image_id="img001",
        source_filename="party.jpg",
        faces=[
            {
                "face_index": 0,
                "detection_confidence": 0.95,
                "identity_id": "id_unnamed_abcd1234",
                "provenance": FACE_PROVENANCE_CLUSTER,
            },
        ],
    )

    monkeypatch.chdir(tmp_path)
    from argparse import Namespace

    from gengallery.commands.faces import run_list_unnamed

    code = run_list_unnamed(
        tmp_path,
        Namespace(
            gallery=None,
            min_faces=1,
            limit=None,
            include_singletons=True,
        ),
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "id_unnamed_abcd1234" in out
    assert "20240715/party.jpg" in out
    assert "1 group(s), 1 face(s)" in out
