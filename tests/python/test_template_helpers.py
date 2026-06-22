"""Tests for Jinja template person-tag helpers."""

from __future__ import annotations

from pathlib import Path

import yaml

from gengallery.services.template_helpers import (
    gallery_person_slugs,
    identity_display_name,
    is_named_identity,
    is_person_auto_tag,
    load_identity_display_names,
    named_identity_slugs,
    named_identity_slugs_from_faces,
    person_auto_tag,
    person_slugs_for_media_item,
)


def test_is_named_identity_filters_anonymous() -> None:
    assert is_named_identity("alice")
    assert not is_named_identity("id_unnamed_abcd")
    assert not is_named_identity(None)


def test_named_identity_slugs_from_faces_collects_distinct_named() -> None:
    faces = [
        {"identity_id": "alice", "provenance": "positive"},
        {"identity_id": "alice", "provenance": "propagated"},
        {"identity_id": "id_unnamed_abcd", "provenance": "cluster"},
        {"identity_id": None, "provenance": "unassigned"},
    ]
    assert named_identity_slugs_from_faces(faces) == ["alice"]


def test_named_identity_slugs_sorts_and_filters() -> None:
    assert named_identity_slugs(["bob", "id_unnamed_x", "alice"]) == ["alice", "bob"]


def test_load_identity_display_names_reads_yaml(tmp_path: Path, monkeypatch) -> None:
    galleries = tmp_path / "galleries"
    galleries.mkdir()
    (galleries / "identities.yaml").write_text(
        yaml.dump(
            {
                "identities": {
                    "alice": {"display_name": "Alice Smith"},
                    "id_unnamed_abcd": {"display_name": "Unknown"},
                }
            }
        )
    )
    monkeypatch.chdir(tmp_path)

    names = load_identity_display_names()
    assert names == {"alice": "Alice Smith"}


def test_identity_display_name_falls_back_to_title_case() -> None:
    assert identity_display_name("bob-jones", {}) == "Bob Jones"


def test_person_auto_tag_and_detection() -> None:
    assert person_auto_tag("alice") == "person:alice"
    assert is_person_auto_tag("person:alice")
    assert not is_person_auto_tag("vacation")


def test_person_slugs_for_media_item_merges_faces_and_tags() -> None:
    item = {
        "faces": [{"identity_id": "alice", "provenance": "positive"}],
        "tags": ["person:bob", "vacation"],
    }
    assert person_slugs_for_media_item(item) == ["alice", "bob"]


def test_gallery_person_slugs_rolls_up_gallery_metadata() -> None:
    gallery = {
        "identities": ["alice"],
        "images": [{"faces": [], "tags": ["person:bob"]}],
        "videos": [],
    }
    assert gallery_person_slugs(gallery) == ["alice", "bob"]
