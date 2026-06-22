"""Tests for canonical image ID resolution across pipeline stages."""

from gengallery.services.image_processor import generate_image_id, resolve_image_id


def test_resolve_image_id_plaintext_matches_generate_image_id() -> None:
    assert resolve_image_id("summer", "photo.jpg", False) == generate_image_id(
        "photo.jpg", "summer"
    )


def test_resolve_image_id_encrypted_uses_sha256_prefix() -> None:
    image_id = resolve_image_id("prom26", "photo.jpg", True)
    assert len(image_id) == 16
    assert image_id == resolve_image_id("prom26", "photo.jpg", True)
