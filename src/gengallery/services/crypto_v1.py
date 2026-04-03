#!/usr/bin/env python

"""
Shared v1 crypto helpers for build-time derivation.
"""

import base64
import hashlib
import hmac

HKDF_HASH_LEN = 32
DERIVED_KEY_LEN = 32
STORAGE_TOKEN_INFO_PREFIX = 'pge/v1/storage_token:'
IMAGE_KEY_INFO = b'pge/v1/key:image'
METADATA_KEY_INFO = b'pge/v1/key:metadata'


def get_gallery_salt_bytes(gallery_id: str) -> bytes:
    """Deterministic public salt for v1: UTF-8 bytes of gallery_id."""
    return gallery_id.encode('utf-8')


def base64url_encode_no_padding(data: bytes) -> str:
    """Encode bytes as base64url without '=' padding."""
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def base64url_decode_no_padding(data: str) -> bytes:
    """Decode base64url text that may omit '=' padding."""
    padding = '=' * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """RFC 5869 HKDF-SHA256."""
    if length <= 0:
        raise ValueError('length must be positive')
    if length > 255 * HKDF_HASH_LEN:
        raise ValueError('length too large for HKDF-SHA256')

    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    output_key_material = b''
    previous_block = b''
    counter = 1
    while len(output_key_material) < length:
        previous_block = hmac.new(
            prk,
            previous_block + info + bytes([counter]),
            hashlib.sha256
        ).digest()
        output_key_material += previous_block
        counter += 1
    return output_key_material[:length]


def derive_storage_token_bytes(password: str, gallery_id: str) -> bytes:
    """Derive 32-byte storage token from password and gallery salt."""
    salt_bytes = get_gallery_salt_bytes(gallery_id)
    info = f'{STORAGE_TOKEN_INFO_PREFIX}{gallery_id}'.encode('utf-8')
    return hkdf_sha256(password.encode('utf-8'), salt_bytes, info, DERIVED_KEY_LEN)


def derive_storage_token(password: str, gallery_id: str) -> str:
    """Derive base64url storage token text from password and gallery id."""
    storage_token_bytes = derive_storage_token_bytes(password, gallery_id)
    return base64url_encode_no_padding(storage_token_bytes)


def derive_storage_token_hash_hex(storage_token_bytes: bytes) -> str:
    """Hex digest of SHA-256(storage_token_bytes)."""
    return hashlib.sha256(storage_token_bytes).hexdigest()


def derive_image_key_bytes(storage_token_bytes: bytes, gallery_id: str) -> bytes:
    """Derive image key bytes from storage token bytes."""
    salt_bytes = get_gallery_salt_bytes(gallery_id)
    return hkdf_sha256(storage_token_bytes, salt_bytes, IMAGE_KEY_INFO, DERIVED_KEY_LEN)


def derive_metadata_key_bytes(storage_token_bytes: bytes, gallery_id: str) -> bytes:
    """Derive metadata key bytes from storage token bytes."""
    salt_bytes = get_gallery_salt_bytes(gallery_id)
    return hkdf_sha256(storage_token_bytes, salt_bytes, METADATA_KEY_INFO, DERIVED_KEY_LEN)
