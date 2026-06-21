"""Face labeling: identities.yaml I/O, path resolution, and CLI mutation helpers.

The ``galleries/identities.yaml`` file is the authoritative source of truth for all
named identities.  This module owns reading and writing it, resolving image paths,
and implementing the ``assign``, ``unassign``, ``reject``, and ``merge`` operations.

Public API
----------
load_identities(project_root)
    Parse identities.yaml → IdentityStore.

save_identities(project_root, store)
    Write IdentityStore back to identities.yaml (atomic rename).

resolve_image_path(project_root, config, path_str)
    Resolve a user-supplied path string → (gallery_id, filename).

assign_face(store, slug, gallery, image, face_index, display_name)
    Add a positive label; auto-create identity if missing.

unassign_face(store, gallery, image, face_index)
    Remove a positive label.

reject_face(store, slug, gallery, image, face_index)
    Add a negative label.

merge_identities(store, source_slug, target_slug)
    Merge source into target; remove source entry.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from gengallery.constants import (
    FACE_SLUG_PATTERN,
    GALLERIES_DIRNAME,
    IDENTITIES_YAML,
)
from gengallery.errors import CliUserError

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FaceRef:
    """A reference to one face in one image (positive or negative label)."""

    gallery: str
    image: str
    face: int | None = None  # None means "the only face" — resolved at apply time

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"gallery": self.gallery, "image": self.image}
        if self.face is not None:
            d["face"] = self.face
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FaceRef:
        return cls(
            gallery=str(d["gallery"]),
            image=str(d["image"]),
            face=d.get("face"),
        )

    def matches(self, gallery: str, image: str, face_index: int | None) -> bool:
        """True when this ref addresses the same face as (gallery, image, face_index)."""
        if self.gallery != gallery or self.image != image:
            return False
        if face_index is None:
            return True
        return self.face is None or self.face == face_index


@dataclass
class IdentityEntry:
    """One named identity with its positive and negative exemplar lists."""

    display_name: str
    positives: list[FaceRef] = field(default_factory=list)
    negatives: list[FaceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"display_name": self.display_name}
        d["positives"] = [r.to_dict() for r in self.positives]
        if self.negatives:
            d["negatives"] = [r.to_dict() for r in self.negatives]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IdentityEntry:
        return cls(
            display_name=str(d.get("display_name", "")),
            positives=[FaceRef.from_dict(r) for r in d.get("positives", [])],
            negatives=[FaceRef.from_dict(r) for r in d.get("negatives", [])],
        )


@dataclass
class IdentityStore:
    """In-memory representation of galleries/identities.yaml."""

    identities: dict[str, IdentityEntry] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identities": {
                slug: entry.to_dict() for slug, entry in self.identities.items()
            }
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IdentityStore:
        store = cls()
        for slug, entry_data in (d.get("identities") or {}).items():
            store.identities[slug] = IdentityEntry.from_dict(entry_data)
        return store


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _identities_path(project_root: Path) -> Path:
    return project_root / IDENTITIES_YAML


def load_identities(project_root: Path) -> IdentityStore:
    """Load galleries/identities.yaml.  Returns an empty store if the file is absent."""
    path = _identities_path(project_root)
    if not path.exists():
        return IdentityStore()
    with path.open() as fh:
        raw = yaml.safe_load(fh)
    if raw is None:
        return IdentityStore()
    if not isinstance(raw, dict):
        raise CliUserError(f"{IDENTITIES_YAML} must be a YAML mapping, not {type(raw).__name__}.")
    return IdentityStore.from_dict(raw)


def save_identities(project_root: Path, store: IdentityStore) -> None:
    """Write IdentityStore to galleries/identities.yaml using an atomic rename."""
    path = _identities_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = store.to_dict()
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_image_path(
    project_root: Path,
    config: dict,
    path_str: str,
) -> tuple[str, str]:
    """Resolve a user-supplied path string to (gallery_id, filename).

    Resolution order (first match wins):
    1. ``{source_path}/{gallery}/{filename}`` when path_str is ``gallery/file.jpg``
    2. ``galleries/{gallery}/{filename}`` relative to project root
    3. Absolute path under project root

    Args:
        project_root: Absolute project root path.
        config: Runtime config dict (must contain ``source_path``).
        path_str: User-supplied path argument.

    Returns:
        (gallery_id, filename) tuple.

    Raises:
        CliUserError: If the path cannot be resolved to an existing image.
    """
    parts = Path(path_str).parts

    # Candidate 1: source_path/gallery/filename
    source = Path(config.get("source_path", GALLERIES_DIRNAME))
    if not source.is_absolute():
        source = project_root / source
    if len(parts) >= 2:
        gallery_id, filename = parts[-2], parts[-1]
        candidate = source / gallery_id / filename
        if candidate.exists():
            return gallery_id, filename

    # Candidate 2: galleries/gallery/filename
    if len(parts) >= 2:
        gallery_id, filename = parts[-2], parts[-1]
        candidate = project_root / GALLERIES_DIRNAME / gallery_id / filename
        if candidate.exists():
            return gallery_id, filename

    # Candidate 3: absolute path that falls under project root
    p = Path(path_str)
    if p.is_absolute() and p.exists():
        try:
            rel = p.relative_to(project_root)
            rel_parts = rel.parts
            if len(rel_parts) >= 2:
                return rel_parts[-2], rel_parts[-1]
        except ValueError:
            pass

    raise CliUserError(
        f"Image not found: {path_str!r}\n"
        "Expected format: gallery_id/filename.jpg  "
        "(e.g. '20240715/portrait.jpg')"
    )


# ---------------------------------------------------------------------------
# Slug validation
# ---------------------------------------------------------------------------


def validate_slug(slug: str) -> None:
    """Raise CliUserError if slug does not match the required pattern."""
    if not re.match(FACE_SLUG_PATTERN, slug):
        raise CliUserError(
            f"Invalid identity slug {slug!r}.  "
            "Slugs must match ^[a-z][a-z0-9-]*$ (lowercase letters, digits, hyphens)."
        )


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------


def assign_face(
    store: IdentityStore,
    slug: str,
    gallery: str,
    image: str,
    face_index: int | None,
    display_name: str | None = None,
) -> None:
    """Add a positive label for (gallery, image, face_index).

    Auto-creates the identity if it does not exist.
    Raises CliUserError if the same (gallery, image, face_index) is already a negative.
    """
    validate_slug(slug)

    if slug not in store.identities:
        name = display_name or slug.replace("-", " ").title()
        store.identities[slug] = IdentityEntry(display_name=name)

    entry = store.identities[slug]

    # Guard: must not already be a negative for this exact face+identity pair
    for neg in entry.negatives:
        if neg.matches(gallery, image, face_index):
            raise CliUserError(
                f"Face ({gallery}/{image} face={face_index}) is already rejected for "
                f"identity '{slug}'.  Use 'faces unassign' to remove the reject first."
            )

    # Deduplicate: skip if an identical positive already exists
    for pos in entry.positives:
        if pos.gallery == gallery and pos.image == image and pos.face == face_index:
            return  # already assigned — idempotent

    entry.positives.append(FaceRef(gallery=gallery, image=image, face=face_index))


def unassign_face(
    store: IdentityStore,
    gallery: str,
    image: str,
    face_index: int | None,
) -> bool:
    """Remove a positive label from whichever identity owns it.

    Returns True if a positive was removed, False if none was found.
    Does NOT remove negatives.
    """
    removed = False
    for entry in store.identities.values():
        before = len(entry.positives)
        entry.positives = [
            p for p in entry.positives if not p.matches(gallery, image, face_index)
        ]
        if len(entry.positives) < before:
            removed = True
    return removed


def reject_face(
    store: IdentityStore,
    slug: str,
    gallery: str,
    image: str,
    face_index: int | None,
) -> None:
    """Add a negative (reject) label for (gallery, image, face_index) → identity.

    Raises CliUserError if the same face+identity pair is already a positive (conflict).
    """
    validate_slug(slug)

    if slug not in store.identities:
        name = slug.replace("-", " ").title()
        store.identities[slug] = IdentityEntry(display_name=name)

    entry = store.identities[slug]

    # Guard: must not already be a positive for this exact face+identity
    for pos in entry.positives:
        if pos.matches(gallery, image, face_index):
            raise CliUserError(
                f"Face ({gallery}/{image} face={face_index}) is already a positive for "
                f"identity '{slug}'.  Use 'faces unassign' to remove the positive first."
            )

    # Deduplicate
    for neg in entry.negatives:
        if neg.gallery == gallery and neg.image == image and neg.face == face_index:
            return  # already rejected — idempotent

    entry.negatives.append(FaceRef(gallery=gallery, image=image, face=face_index))


def merge_identities(
    store: IdentityStore,
    source_slug: str,
    target_slug: str,
) -> None:
    """Merge source identity into target.

    - Positives from source move to target; conflicting (same face) ones are dropped
      (target wins per spec).
    - Negatives from source move to target (deduplicated).
    - Source entry is removed.

    Raises CliUserError if source == target or either slug is unknown.
    """
    if source_slug == target_slug:
        raise CliUserError("Cannot merge an identity into itself.")
    if source_slug not in store.identities:
        raise CliUserError(f"Unknown identity: '{source_slug}'")
    if target_slug not in store.identities:
        raise CliUserError(f"Unknown identity: '{target_slug}'")

    src = store.identities[source_slug]
    tgt = store.identities[target_slug]

    # Merge positives: target wins on conflict (same gallery+image+face)
    existing_positive_keys = {
        (p.gallery, p.image, p.face) for p in tgt.positives
    }
    for pos in src.positives:
        key = (pos.gallery, pos.image, pos.face)
        if key not in existing_positive_keys:
            tgt.positives.append(pos)
            existing_positive_keys.add(key)

    # Merge negatives (deduplicate)
    existing_negative_keys = {
        (n.gallery, n.image, n.face) for n in tgt.negatives
    }
    for neg in src.negatives:
        key = (neg.gallery, neg.image, neg.face)
        if key not in existing_negative_keys:
            tgt.negatives.append(neg)
            existing_negative_keys.add(key)

    del store.identities[source_slug]
