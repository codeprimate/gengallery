import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const {
  buildStorageTokenKey,
  resolveProtectedGalleryPage,
  getLegacyStorageKeysForGallery,
  clearStorageKeysForGallery
} = require('../../templates/site.js');

test('buildStorageTokenKey uses versioned gallery namespace', () => {
  assert.equal(buildStorageTokenKey('gallery-123'), 'pge.v1.storage_token.gallery-123');
});

test('legacy key discovery includes known stale key patterns', () => {
  const legacyKeys = getLegacyStorageKeysForGallery('abc');
  assert.deepEqual(legacyKeys, [
    'gallery_abc_private_id',
    'pge.storage_token.abc',
    'storage_token.abc',
    'storage_token_abc'
  ]);
});

test('protected gallery page resolver falls back safely', () => {
  assert.equal(resolveProtectedGalleryPage('abc123def4567890.html'), 'abc123def4567890.html');
  assert.equal(resolveProtectedGalleryPage('  abc123def4567890.html  '), 'abc123def4567890.html');
  assert.equal(resolveProtectedGalleryPage(''), 'gallery.html');
  assert.equal(resolveProtectedGalleryPage(undefined), 'gallery.html');
});

test('logout cleanup removes namespaced token and stale keys', () => {
  const keyValues = new Map([
    ['pge.v1.storage_token.abc', 'token'],
    ['gallery_abc_private_id', 'legacy'],
    ['pge.storage_token.abc', 'legacy2'],
    ['storage_token.abc', 'legacy3'],
    ['storage_token_abc', 'legacy4'],
    ['unrelated.key', 'keep']
  ]);

  const storage = {
    removeItem(key) {
      keyValues.delete(key);
    }
  };

  clearStorageKeysForGallery(storage, 'abc');

  assert.equal(keyValues.has('pge.v1.storage_token.abc'), false);
  assert.equal(keyValues.has('gallery_abc_private_id'), false);
  assert.equal(keyValues.has('pge.storage_token.abc'), false);
  assert.equal(keyValues.has('storage_token.abc'), false);
  assert.equal(keyValues.has('storage_token_abc'), false);
  assert.equal(keyValues.get('unrelated.key'), 'keep');
});
