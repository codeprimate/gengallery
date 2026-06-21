"""Unit tests for face_labeling: YAML I/O, path resolution, and label mutations."""

from __future__ import annotations

from pathlib import Path

import pytest

from gengallery.errors import CliUserError
from gengallery.services.face_labeling import (
    IdentityEntry,
    IdentityStore,
    assign_face,
    load_identities,
    merge_identities,
    reject_face,
    resolve_image_path,
    save_identities,
    unassign_face,
    validate_slug,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(*slugs: str) -> IdentityStore:
    store = IdentityStore()
    for slug in slugs:
        store.identities[slug] = IdentityEntry(display_name=slug.title())
    return store


# ---------------------------------------------------------------------------
# Slug validation
# ---------------------------------------------------------------------------


def test_validate_slug_valid() -> None:
    for s in ("alice", "bob-smith", "p123", "a"):
        validate_slug(s)  # no exception


def test_validate_slug_invalid() -> None:
    for bad in ("", "Alice", "bob smith", "123abc", "-start", "has_underscore"):
        with pytest.raises(CliUserError):
            validate_slug(bad)


# ---------------------------------------------------------------------------
# load / save round-trip
# ---------------------------------------------------------------------------


def test_load_identities_missing_file(tmp_path: Path) -> None:
    store = load_identities(tmp_path)
    assert store.identities == {}


def test_load_identities_empty_yaml(tmp_path: Path) -> None:
    (tmp_path / "galleries").mkdir()
    (tmp_path / "galleries" / "identities.yaml").write_text("")
    store = load_identities(tmp_path)
    assert store.identities == {}


def test_save_and_reload_round_trip(tmp_path: Path) -> None:
    store = IdentityStore()
    assign_face(store, "alice", "20240101", "portrait.jpg", None)
    reject_face(store, "alice", "20240101", "other.jpg", 0)

    save_identities(tmp_path, store)
    loaded = load_identities(tmp_path)

    assert "alice" in loaded.identities
    assert len(loaded.identities["alice"].positives) == 1
    assert len(loaded.identities["alice"].negatives) == 1


# ---------------------------------------------------------------------------
# assign
# ---------------------------------------------------------------------------


def test_assign_creates_identity() -> None:
    store = IdentityStore()
    assign_face(store, "alice", "20240101", "portrait.jpg", None)
    assert "alice" in store.identities
    assert len(store.identities["alice"].positives) == 1


def test_assign_auto_display_name() -> None:
    store = IdentityStore()
    assign_face(store, "bob-smith", "20240101", "photo.jpg", None)
    assert store.identities["bob-smith"].display_name == "Bob Smith"


def test_assign_idempotent() -> None:
    store = IdentityStore()
    assign_face(store, "alice", "20240101", "portrait.jpg", 0)
    assign_face(store, "alice", "20240101", "portrait.jpg", 0)
    assert len(store.identities["alice"].positives) == 1


def test_assign_conflict_with_negative_raises() -> None:
    store = IdentityStore()
    reject_face(store, "alice", "20240101", "photo.jpg", 0)
    with pytest.raises(CliUserError, match="already rejected"):
        assign_face(store, "alice", "20240101", "photo.jpg", 0)


def test_assign_multi_face_requires_explicit_index() -> None:
    """Assigning None (implicit single face) to an image with 2 faces is ambiguous at apply time.
    However, the YAML mutation itself allows face=None — disambiguation happens at apply time."""
    store = IdentityStore()
    # face=None is allowed in YAML — caller (CLI) must check detection count first
    assign_face(store, "alice", "gallery", "img.jpg", None)
    assert store.identities["alice"].positives[0].face is None


# ---------------------------------------------------------------------------
# unassign
# ---------------------------------------------------------------------------


def test_unassign_removes_positive() -> None:
    store = IdentityStore()
    assign_face(store, "alice", "gal", "img.jpg", None)
    removed = unassign_face(store, "gal", "img.jpg", None)
    assert removed is True
    assert store.identities["alice"].positives == []


def test_unassign_returns_false_when_not_found() -> None:
    store = _make_store("alice")
    removed = unassign_face(store, "gal", "missing.jpg", None)
    assert removed is False


def test_unassign_does_not_remove_negatives() -> None:
    store = IdentityStore()
    reject_face(store, "alice", "gal", "img.jpg", 0)
    unassign_face(store, "gal", "img.jpg", 0)
    assert len(store.identities["alice"].negatives) == 1


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------


def test_reject_creates_negative() -> None:
    store = IdentityStore()
    reject_face(store, "alice", "gal", "img.jpg", 1)
    assert len(store.identities["alice"].negatives) == 1


def test_reject_idempotent() -> None:
    store = IdentityStore()
    reject_face(store, "alice", "gal", "img.jpg", 1)
    reject_face(store, "alice", "gal", "img.jpg", 1)
    assert len(store.identities["alice"].negatives) == 1


def test_reject_conflict_with_positive_raises() -> None:
    store = IdentityStore()
    assign_face(store, "alice", "gal", "img.jpg", 0)
    with pytest.raises(CliUserError, match="already a positive"):
        reject_face(store, "alice", "gal", "img.jpg", 0)


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def test_merge_moves_positives_to_target() -> None:
    store = _make_store("alice", "bob")
    assign_face(store, "alice", "gal", "a.jpg", None)
    merge_identities(store, "alice", "bob")
    assert "alice" not in store.identities
    assert len(store.identities["bob"].positives) == 1


def test_merge_target_wins_on_conflict() -> None:
    store = _make_store("alice", "bob")
    assign_face(store, "alice", "gal", "same.jpg", 0)
    assign_face(store, "bob", "gal", "same.jpg", 0)
    merge_identities(store, "alice", "bob")
    # Target bob keeps its own positive; source duplicate is dropped
    assert len(store.identities["bob"].positives) == 1


def test_merge_self_raises() -> None:
    store = _make_store("alice")
    with pytest.raises(CliUserError, match="itself"):
        merge_identities(store, "alice", "alice")


def test_merge_unknown_source_raises() -> None:
    store = _make_store("bob")
    with pytest.raises(CliUserError, match="Unknown identity"):
        merge_identities(store, "nobody", "bob")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _make_gallery(tmp_path: Path, gallery_id: str, filename: str) -> None:
    (tmp_path / "galleries" / gallery_id).mkdir(parents=True)
    (tmp_path / "galleries" / gallery_id / filename).touch()


def test_resolve_image_path_gallery_slash_file(tmp_path: Path) -> None:
    _make_gallery(tmp_path, "20240101", "portrait.jpg")
    config = {"source_path": str(tmp_path / "galleries")}
    gid, fname = resolve_image_path(tmp_path, config, "20240101/portrait.jpg")
    assert gid == "20240101"
    assert fname == "portrait.jpg"


def test_resolve_image_path_not_found_raises(tmp_path: Path) -> None:
    config = {"source_path": str(tmp_path / "galleries")}
    with pytest.raises(CliUserError, match="Image not found"):
        resolve_image_path(tmp_path, config, "missing/image.jpg")
