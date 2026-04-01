#!/usr/bin/env python

"""
Envelope-v1 serialization/parsing helpers for encrypted gallery artifacts.
"""

import os
import struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b'PGE1'
FORMAT_VERSION = 1
CRYPTO_SUITE_AES_256_GCM = 1
FLAGS_NONE = 0
RESERVED_BYTE = 0
NONCE_LENGTH_BYTES = 12
HEADER_LENGTH_FIELD_BYTES = 4
MIN_CIPHERTEXT_WITH_TAG_BYTES = 16


def serialize_envelope(
    nonce: bytes,
    ciphertext_with_tag: bytes,
    plaintext_header: bytes = b''
) -> bytes:
    """Serialize envelope-v1 bytes with fixed header fields."""
    if len(nonce) != NONCE_LENGTH_BYTES:
        raise ValueError('nonce must be 12 bytes')
    if len(ciphertext_with_tag) < MIN_CIPHERTEXT_WITH_TAG_BYTES:
        raise ValueError('ciphertext must include GCM tag')

    header_length = len(plaintext_header)
    fixed_header = b''.join([
        MAGIC,
        bytes([FORMAT_VERSION]),
        bytes([CRYPTO_SUITE_AES_256_GCM]),
        bytes([FLAGS_NONE]),
        bytes([RESERVED_BYTE]),
        struct.pack('>I', header_length),
    ])
    return fixed_header + plaintext_header + nonce + ciphertext_with_tag


def parse_envelope(envelope_bytes: bytes) -> dict:
    """Parse and validate envelope-v1 bytes."""
    minimum_size = len(MAGIC) + 1 + 1 + 1 + 1 + HEADER_LENGTH_FIELD_BYTES + NONCE_LENGTH_BYTES + MIN_CIPHERTEXT_WITH_TAG_BYTES
    if len(envelope_bytes) < minimum_size:
        raise ValueError('envelope too short')

    if envelope_bytes[:4] != MAGIC:
        raise ValueError('bad envelope magic')

    version = envelope_bytes[4]
    suite = envelope_bytes[5]
    flags = envelope_bytes[6]
    reserved = envelope_bytes[7]
    header_length = struct.unpack('>I', envelope_bytes[8:12])[0]

    if version != FORMAT_VERSION:
        raise ValueError('unsupported envelope version')
    if suite != CRYPTO_SUITE_AES_256_GCM:
        raise ValueError('unsupported crypto suite')
    if reserved != RESERVED_BYTE:
        raise ValueError('invalid reserved byte')

    header_start = 12
    header_end = header_start + header_length
    nonce_end = header_end + NONCE_LENGTH_BYTES
    if nonce_end > len(envelope_bytes):
        raise ValueError('invalid header length')

    ciphertext_with_tag = envelope_bytes[nonce_end:]
    if len(ciphertext_with_tag) < MIN_CIPHERTEXT_WITH_TAG_BYTES:
        raise ValueError('ciphertext/tag truncated')

    return {
        'version': version,
        'suite': suite,
        'flags': flags,
        'plaintext_header': envelope_bytes[header_start:header_end],
        'nonce': envelope_bytes[header_end:nonce_end],
        'ciphertext_with_tag': ciphertext_with_tag,
    }


def encrypt_payload(
    plaintext: bytes,
    key_bytes: bytes,
    plaintext_header: bytes = b''
) -> bytes:
    """Encrypt plaintext as envelope-v1 AES-256-GCM."""
    if len(key_bytes) != 32:
        raise ValueError('AES-256-GCM key must be 32 bytes')

    nonce = os.urandom(NONCE_LENGTH_BYTES)
    aesgcm = AESGCM(key_bytes)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    return serialize_envelope(nonce, ciphertext_with_tag, plaintext_header)


def decrypt_payload(envelope_bytes: bytes, key_bytes: bytes) -> bytes:
    """Decrypt envelope-v1 AES-256-GCM payload."""
    if len(key_bytes) != 32:
        raise ValueError('AES-256-GCM key must be 32 bytes')

    parsed = parse_envelope(envelope_bytes)
    aesgcm = AESGCM(key_bytes)
    return aesgcm.decrypt(parsed['nonce'], parsed['ciphertext_with_tag'], None)
