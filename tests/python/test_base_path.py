"""Tests for configurable base_path URL prefixing."""

from __future__ import annotations

import json

import pytest

from gengallery.pathing import load_project_config
from gengallery.services import image_processor
from gengallery.services.gallery_processor import create_manifest_dict, get_variant_url
from gengallery.services.generator import create_jinja_environment
from gengallery.services.urls import (
    base_path_from_config,
    normalize_base_path,
    translate_request_path,
    url,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, ""),
        ("", ""),
        ("/", ""),
        ("/gallery", "/gallery"),
        ("/gallery/", "/gallery"),
        ("gallery", "gallery"),
    ],
)
def test_normalize_base_path(raw: str | None, expected: str) -> None:
    assert normalize_base_path(raw) == expected


@pytest.mark.parametrize(
    ("path", "base_path", "expected"),
    [
        ("/css/tailwind.css", "", "/css/tailwind.css"),
        ("/css/tailwind.css", "/gallery", "/gallery/css/tailwind.css"),
        ("/galleries/x/y.jpg", "/gallery", "/gallery/galleries/x/y.jpg"),
        ("https://cdn.example.com/lib.js", "/gallery", "https://cdn.example.com/lib.js"),
        ("/", "/gallery", "/gallery/"),
        ("/", "", "/"),
        ("relative.css", "/gallery", "/gallery/relative.css"),
    ],
)
def test_url_prefixes_root_relative_paths(path: str, base_path: str, expected: str) -> None:
    assert url(path, base_path) == expected


def test_url_is_idempotent_when_path_already_prefixed() -> None:
    prefixed = "/gallery/galleries/x/full/y.jpg"
    assert url(prefixed, "/gallery") == prefixed
    assert url(prefixed, "/gallery/") == prefixed


def test_url_leaves_protocol_relative_paths_untouched() -> None:
    assert url("//cdn.example.com/lib.js", "/gallery") == "//cdn.example.com/lib.js"


@pytest.mark.parametrize(
    ("request_path", "base_path", "expected"),
    [
        ("/gallery/css/site.css", "/gallery", "/css/site.css"),
        ("/gallery", "/gallery", "/"),
        ("/gallery/", "/gallery/", "/"),
        ("/css/site.css", "/gallery", "/css/site.css"),
        ("/", "", "/"),
    ],
)
def test_translate_request_path_strips_prefix(
    request_path: str, base_path: str, expected: str
) -> None:
    assert translate_request_path(request_path, base_path) == expected


def test_load_project_config_normalizes_base_path(tmp_path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text('site_name: x\nbase_path: "/gallery/"\n', encoding="utf-8")
    data = load_project_config(tmp_path)
    assert data["base_path"] == "/gallery"


def test_apply_runtime_config_normalizes_base_path() -> None:
    image_processor.apply_runtime_config({"base_path": "/gallery/"})
    assert image_processor.config["base_path"] == "/gallery"


def test_create_jinja_environment_exposes_normalized_base_path() -> None:
    env = create_jinja_environment({"base_path": "/gallery/"})
    assert env.globals["base_path"] == "/gallery"


def test_get_variant_url_returns_stored_path_without_double_prefix() -> None:
    image_processor.apply_runtime_config({"base_path": "/gallery", "image_sizes": {"full": 1}})
    stored = url("/galleries/g1/full/img1.jpg", "/gallery")
    metadata = {"id": "img1", "path": stored, "thumbnail_path": url("/galleries/g1/thumbnail/img1.jpg", "/gallery")}
    assert get_variant_url(metadata, "g1", "full") == stored
    assert get_variant_url(metadata, "g1", "thumbnail") == metadata["thumbnail_path"]


def test_create_manifest_dict_does_not_double_prefix_metadata_urls() -> None:
    image_processor.apply_runtime_config(
        {
            "base_path": "/gallery",
            "image_sizes": {"full": 3840, "thumbnail": 450},
        }
    )
    gallery_data = {
        "id": "g1",
        "encrypted": True,
        "storage_token_hash_hex": "abc",
        "images": [
            {
                "id": "img1",
                "path": url("/galleries/g1/full/img1.enc", "/gallery"),
                "thumbnail_path": url("/galleries/g1/thumbnail/img1.enc", "/gallery"),
                "metadata_path": url("/galleries/g1/metadata/img1.enc", "/gallery"),
            }
        ],
        "videos": [
            {
                "id": "vid1",
                "thumbnail_path": url("/galleries/g1/thumbnail/vid1.enc", "/gallery"),
                "playback_path": url("/galleries/g1/video/vid1.enc", "/gallery"),
                "metadata_path": url("/galleries/g1/metadata/vid1.enc", "/gallery"),
            }
        ],
    }

    manifest = create_manifest_dict(gallery_data)

    assert manifest["images"][0]["variants"]["full"]["url"] == gallery_data["images"][0]["path"]
    assert manifest["images"][0]["metadata_url"] == gallery_data["images"][0]["metadata_path"]
    assert manifest["videos"][0]["variants"]["thumbnail"]["url"] == gallery_data["videos"][0]["thumbnail_path"]
    assert manifest["videos"][0]["metadata_url"] == gallery_data["videos"][0]["metadata_path"]

    serialized = json.dumps(manifest)
    assert "/gallery/gallery/" not in serialized


def test_base_path_from_config_handles_missing_key() -> None:
    assert base_path_from_config({}) == ""
    assert base_path_from_config(None) == ""
