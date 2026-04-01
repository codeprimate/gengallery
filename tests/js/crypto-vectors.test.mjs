import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';

const FIXTURE_PATH = 'fixtures/crypto/v1_vectors.json';
const STORAGE_TOKEN_INFO_PREFIX = 'pge/v1/storage_token:';
const IMAGE_KEY_INFO = 'pge/v1/key:image';
const METADATA_KEY_INFO = 'pge/v1/key:metadata';
const DERIVED_KEY_LENGTH_BYTES = 32;

const subtle = crypto.webcrypto.subtle;

function utf8Bytes(value) {
  return new TextEncoder().encode(value);
}

function hexToBytes(value) {
  return Uint8Array.from(Buffer.from(value, 'hex'));
}

function bytesToHex(value) {
  return Buffer.from(value).toString('hex');
}

function bytesToBase64url(value) {
  return Buffer.from(value).toString('base64url');
}

async function sha256Hex(inputBytes) {
  const digest = await subtle.digest('SHA-256', inputBytes);
  return bytesToHex(new Uint8Array(digest));
}

async function hkdfSha256(ikmBytes, saltBytes, infoBytes, lengthBytes) {
  const keyMaterial = await subtle.importKey('raw', ikmBytes, 'HKDF', false, ['deriveBits']);
  const bits = await subtle.deriveBits(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: saltBytes,
      info: infoBytes
    },
    keyMaterial,
    lengthBytes * 8
  );
  return new Uint8Array(bits);
}

function parseEnvelopeV1Hex(envelopeHex) {
  const bytes = hexToBytes(envelopeHex);
  const magic = Buffer.from(bytes.slice(0, 4)).toString('ascii');
  assert.equal(magic, 'PGE1');
  assert.equal(bytes[4], 1);
  assert.equal(bytes[5], 1);
  const headerLength = (bytes[8] << 24) | (bytes[9] << 16) | (bytes[10] << 8) | bytes[11];
  const nonceStart = 12 + headerLength;
  const nonceEnd = nonceStart + 12;
  return {
    nonce: bytes.slice(nonceStart, nonceEnd),
    ciphertextWithTag: bytes.slice(nonceEnd)
  };
}

const vectors = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8')).vectors;

test('kdf vectors match fixture in JS runtime', async () => {
  for (const vector of vectors) {
    const saltBytes = utf8Bytes(vector.gallery_id);
    assert.equal(bytesToHex(saltBytes), vector.salt_utf8_hex);

    const storageTokenBytes = await hkdfSha256(
      utf8Bytes(vector.password),
      saltBytes,
      utf8Bytes(`${STORAGE_TOKEN_INFO_PREFIX}${vector.gallery_id}`),
      DERIVED_KEY_LENGTH_BYTES
    );
    assert.equal(bytesToBase64url(storageTokenBytes), vector.storage_token_b64url);
    assert.equal(await sha256Hex(storageTokenBytes), vector.storage_token_hash_hex);

    const imageKeyBytes = await hkdfSha256(
      storageTokenBytes,
      saltBytes,
      utf8Bytes(IMAGE_KEY_INFO),
      DERIVED_KEY_LENGTH_BYTES
    );
    const metadataKeyBytes = await hkdfSha256(
      storageTokenBytes,
      saltBytes,
      utf8Bytes(METADATA_KEY_INFO),
      DERIVED_KEY_LENGTH_BYTES
    );
    assert.equal(bytesToHex(imageKeyBytes), vector.image_key_hex);
    assert.equal(bytesToHex(metadataKeyBytes), vector.metadata_key_hex);
  }
});

test('js decrypts python envelope vector', async () => {
  for (const vector of vectors) {
    const parsed = parseEnvelopeV1Hex(vector.envelope_hex);
    assert.equal(bytesToHex(parsed.nonce), vector.nonce_hex);
    assert.equal(bytesToHex(parsed.ciphertextWithTag), vector.ciphertext_with_tag_hex);

    const key = await subtle.importKey(
      'raw',
      hexToBytes(vector.image_key_hex),
      { name: 'AES-GCM' },
      false,
      ['decrypt']
    );
    const plaintext = await subtle.decrypt(
      { name: 'AES-GCM', iv: parsed.nonce },
      key,
      parsed.ciphertextWithTag
    );
    assert.equal(new TextDecoder().decode(new Uint8Array(plaintext)), vector.plaintext_utf8);
  }
});
