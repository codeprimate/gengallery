import json
import os
import sys

FIXTURE_PATH = os.path.join("fixtures", "crypto", "v1_vectors.json")
BIN_PATH = os.path.abspath("bin")
if BIN_PATH not in sys.path:
    sys.path.insert(0, BIN_PATH)

from crypto_v1 import (  # noqa: E402
    derive_image_key_bytes,
    derive_metadata_key_bytes,
    derive_storage_token,
    derive_storage_token_bytes,
    derive_storage_token_hash_hex,
    get_gallery_salt_bytes,
)
from envelope_v1 import decrypt_payload, encrypt_payload, parse_envelope  # noqa: E402


def load_vectors():
    with open(FIXTURE_PATH) as fixture_file:
        return json.load(fixture_file)["vectors"]


def test_kdf_vectors_match_fixture():
    for vector in load_vectors():
        password = vector["password"]
        gallery_id = vector["gallery_id"]
        storage_token_bytes = derive_storage_token_bytes(password, gallery_id)

        assert get_gallery_salt_bytes(gallery_id).hex() == vector["salt_utf8_hex"]
        assert derive_storage_token(password, gallery_id) == vector["storage_token_b64url"]
        assert (
            derive_storage_token_hash_hex(storage_token_bytes) == vector["storage_token_hash_hex"]
        )
        assert (
            derive_image_key_bytes(storage_token_bytes, gallery_id).hex() == vector["image_key_hex"]
        )
        assert (
            derive_metadata_key_bytes(storage_token_bytes, gallery_id).hex()
            == vector["metadata_key_hex"]
        )


def test_envelope_vector_round_trip():
    for vector in load_vectors():
        envelope_bytes = bytes.fromhex(vector["envelope_hex"])
        parsed = parse_envelope(envelope_bytes)
        assert parsed["nonce"].hex() == vector["nonce_hex"]
        assert parsed["ciphertext_with_tag"].hex() == vector["ciphertext_with_tag_hex"]

        image_key = bytes.fromhex(vector["image_key_hex"])
        plaintext = decrypt_payload(envelope_bytes, image_key)
        assert plaintext.decode("utf-8") == vector["plaintext_utf8"]


def test_encrypt_payload_with_nonce_material_is_deterministic():
    key = bytes(32)
    material = b"pge-test|gallery-a|img-1|full"
    pt = b"hello"
    first = encrypt_payload(pt, key, nonce_material=material)
    second = encrypt_payload(pt, key, nonce_material=material)
    assert first == second
    assert decrypt_payload(first, key) == pt
