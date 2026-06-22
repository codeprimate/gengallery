"""Jinja template helpers for person identity display."""

from __future__ import annotations

import os

import yaml

from gengallery.constants import (
    FACE_ANONYMOUS_IDENTITY_PREFIX,
    FACE_DEFAULT_AUTO_TAG_PREFIX,
    IDENTITIES_YAML,
)


def is_named_identity(slug: str | None) -> bool:
    """True when slug is a named identity (not anonymous cluster id)."""
    return bool(slug) and not str(slug).startswith(FACE_ANONYMOUS_IDENTITY_PREFIX)


def named_identity_slugs(slugs: list[str] | None) -> list[str]:
    """Return sorted named identity slugs from a slug list."""
    return sorted(s for s in (slugs or []) if is_named_identity(s))


def person_slugs_from_tags(
    tags: list[str] | None,
    auto_tag_prefix: str = FACE_DEFAULT_AUTO_TAG_PREFIX,
) -> list[str]:
    """Extract named identity slugs from person:* auto-tags on an item."""
    slugs: set[str] = set()
    for tag in tags or []:
        tag_str = str(tag)
        if not tag_str.startswith(auto_tag_prefix):
            continue
        slug = tag_str[len(auto_tag_prefix):]
        if is_named_identity(slug):
            slugs.add(slug)
    return sorted(slugs)


def person_slugs_for_media_item(
    item: dict,
    auto_tag_prefix: str = FACE_DEFAULT_AUTO_TAG_PREFIX,
) -> list[str]:
    """Collect named person slugs from faces[] and person:* tags on one media item."""
    slugs = set(named_identity_slugs_from_faces(item.get("faces")))
    slugs.update(person_slugs_from_tags(item.get("tags"), auto_tag_prefix))
    return sorted(slugs)


def gallery_person_slugs(
    gallery: dict,
    auto_tag_prefix: str = FACE_DEFAULT_AUTO_TAG_PREFIX,
) -> list[str]:
    """Collect named person slugs for a gallery header from identities and item metadata."""
    slugs = set(named_identity_slugs(gallery.get("identities")))
    for item in (gallery.get("images") or []) + (gallery.get("videos") or []):
        slugs.update(person_slugs_for_media_item(item, auto_tag_prefix))
    return sorted(slugs)


def named_identity_slugs_from_faces(faces: list[dict] | None) -> list[str]:
    """Collect distinct named identity slugs from export faces[] records."""
    slugs: set[str] = set()
    for face in faces or []:
        identity_id = face.get("identity_id")
        if is_named_identity(identity_id):
            slugs.add(str(identity_id))
    return sorted(slugs)


def load_identity_display_names(
    auto_tag_prefix: str = FACE_DEFAULT_AUTO_TAG_PREFIX,
) -> dict[str, str]:
    """Load identity slug → display name from galleries/identities.yaml."""
    if not os.path.exists(IDENTITIES_YAML):
        return {}

    with open(IDENTITIES_YAML) as fh:
        data = yaml.safe_load(fh) or {}

    names: dict[str, str] = {}
    for slug, entry in (data.get("identities") or {}).items():
        if not is_named_identity(slug):
            continue
        display_name = ""
        if isinstance(entry, dict):
            display_name = str(entry.get("display_name") or "").strip()
        names[str(slug)] = display_name or str(slug).replace("-", " ").title()
    return names


def identity_display_name(slug: str, display_names: dict[str, str]) -> str:
    """Resolve a slug to its display label."""
    return display_names.get(slug) or str(slug).replace("-", " ").title()


def person_auto_tag(slug: str, auto_tag_prefix: str = FACE_DEFAULT_AUTO_TAG_PREFIX) -> str:
    """Build the auto-managed person tag string for tag listing links."""
    return f"{auto_tag_prefix}{slug}"


def is_person_auto_tag(tag: str, auto_tag_prefix: str = FACE_DEFAULT_AUTO_TAG_PREFIX) -> bool:
    """True when tag is a system-managed person auto-tag."""
    return str(tag).startswith(auto_tag_prefix)


def build_template_globals(
    display_names: dict[str, str],
    auto_tag_prefix: str = FACE_DEFAULT_AUTO_TAG_PREFIX,
) -> dict:
    """Return Jinja globals for gallery and image templates."""
    return {
        "is_named_identity": is_named_identity,
        "named_identity_slugs": named_identity_slugs,
        "named_identity_slugs_from_faces": named_identity_slugs_from_faces,
        "person_slugs_for_media_item": lambda item: person_slugs_for_media_item(item, auto_tag_prefix),
        "gallery_person_slugs": lambda gallery: gallery_person_slugs(gallery, auto_tag_prefix),
        "identity_display_name": lambda slug: identity_display_name(slug, display_names),
        "person_auto_tag": lambda slug: person_auto_tag(slug, auto_tag_prefix),
        "is_person_auto_tag": lambda tag: is_person_auto_tag(tag, auto_tag_prefix),
    }
