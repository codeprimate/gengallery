# Feature: gengallery `base_path` Configuration

## Problem Statement

gengallery generates HTML with root-absolute paths (`/galleries/...`, `/css/...`, `/`) at build time. When the output is served under a URL subpath (e.g. Hexate nginx mounts at `/gallery/`), every in-page link and asset reference resolves to the wrong URL and returns 404.

Current symptom in Hexate:

| Generated in HTML | Resolves to | Result |
|---|---|---|
| `href="/galleries/session-foo/d242b0dc3ba3.html"` | `http://host:9999/galleries/...` | 404 |
| `src="/css/tailwind.css"` | `http://host:9999/css/...` | 404 |
| `href="/"` (home) | `http://host:9999/` | 404 |

The gallery *entry* URL works only because nginx maps `/gallery/` → `public_html/`. Internal links omit that prefix.

## Requirements

### Functional Requirements
- Add an optional `base_path` string to `config.yaml` (default `""` for backward compatibility)
- When `base_path` is non-empty, all URL paths in generated HTML must be prefixed with it
- When `base_path` is empty/absent, behavior must be identical to today — zero regression risk
- Static files (CSS, JS, favicon, robots.txt) written to disk must remain at their current filesystem locations — only the *URL references* change

### Technical Constraints
- **Two distinct path layers**: filesystem output paths (on disk under `public_html/`) stay unchanged; only URL strings (in metadata and HTML) are prefixed
- **Six URL surfaces** must be covered:
  1. Image metadata dict fields (`url`, `path`, `thumbnail_path`, `cover_path`, `metadata_path`)
  2. Video metadata dict fields (`url`, `thumbnail_path`, `playback_path`, `metadata_path`)
  3. Manifest file path (`manifest_path` in gallery data + JSON content)
  4. Gallery cover references (`cover.path`, `cover.thumbnail_path`)
  5. All Jinja3 template hardcoded `href="/..."`, `src="/..."`, and link fragments
  6. Tag hash page paths in both template hrefs and generator output mapping

### Edge Cases & Error Handling
- `base_path: ""` or absent key → current behavior, no prefix added
- `base_path: "/"` → double-slash risk on paths like `//css/tailwind.css` — must normalize or reject
- `base_path: "/gallery"` (no trailing slash) → safe, paths become `/gallery/galleries/...`
- `base_path` with trailing slash (`"/gallery/"`) → `/gallery//galleries/...` — must strip trailing slash at load time
- Server-side file writes (e.g. `write_manifest_file` returning URL path) — must NOT prefix the JSON content URLs, since those are consumed client-side by JS and must match the actual accessible URL
- Encrypted/manifest URLs in JSON responses must be prefixed consistently with the rest
- The `serve` command's HTTP server strips `base_path` from incoming request paths via a custom handler subclass, so local dev works transparently with the prefix

## Technical Approach

### Implementation Strategy

**Add `base_path` to config.** A single optional string key. Load into the mutable `config` dict like every other setting. Normalize at load time: strip trailing slash, default `""`.

**Create a URL helper module** (`src/gengallery/services/urls.py`):

```python
# Public API
def set_base_path(path: str) -> None: ...
def base_path() -> str: ...
def url(path: str) -> str:
    """Prepend base_path to a root-relative URL path.
    Return the path unchanged if it's absolute (http://...) or base_path is empty."""
    ...
```

**Apply in metadata construction.** In `create_metadata_dict()` (image_processor), `create_video_metadata_dict()` (video_processor), and `write_manifest_file()` (gallery_processor), wrap all URL string literals with `url()`:

```python
# Before
"url": f"/galleries/{gallery_id}/{image_id}.html",
# After
"url": url(f"/galleries/{gallery_id}/{image_id}.html"),
```

**Apply in Jinja templates.** Pass `base_path` as a template global. Replace every root-absolute static path in all 10 `.jinja` files:

```
# Before:
<link href="/css/tailwind.css" ...>
<a href="/"> ... </a>
<a href="/galleries/{{ gallery.id }}/index.html">
<script src="/js/site.js">

# After:
<link href="{{ base_path }}/css/tailwind.css" ...>
<a href="{{ base_path or '/' }}"> ... </a>
<a href="{{ base_path }}/galleries/{{ gallery.id }}/index.html">
<script src="{{ base_path }}/js/site.js">
```

**Apply in generator.py.** The `generate_gallery_listing_pages` function writes files at `f'{tag_hash}.html'` and links to them as `href="/{tag_hash}.html"`. Both the generated file paths (on disk) AND the template URLs must be handled:
- On-disk path stays unchanged relative to `public_html/`: `os.path.join(public_html, f'{tag_hash}.html')`
- Template context gets `base_path` so `{{ base_path }}/{tag_hash}.html` links correctly

**`serve` command — `PrefixedHTTPRequestHandler`.** A single subclass of `SimpleHTTPRequestHandler` overrides `translate_path()` to strip the base prefix before resolving to the filesystem, so local dev works transparently:

```python
class PrefixedHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, base_path="", directory=None, **kwargs):
        self.base_path = base_path.rstrip("/")
        super().__init__(*args, directory=directory, **kwargs)

    def translate_path(self, path):
        if self.base_path and path.startswith(self.base_path + "/"):
            path = path[len(self.base_path):]
        elif self.base_path and path == self.base_path:
            path = "/"
        return super().translate_path(path)
```

`send_head()` already handles the trailing-slash redirect on the original prefixed path, so `/gallery` → `/gallery/` works without extra logic. The handler is selected in `run_serve()`: if `base_path` is set, use the prefixed variant; otherwise use plain `SimpleHTTPRequestHandler` (identical behavior).

The serve URL message prints the prefixed address when `base_path` is set (e.g. `http://127.0.0.1:8000/gallery/`).

### Affected Components

**Metadata dict URL fields** (7 string literals across 2 files):
- `src/gengallery/services/image_processor.py` — lines 474-477, 486  (`url`, `path`, `thumbnail_path`, `cover_path`, `metadata_path`)
- `src/gengallery/services/video_processor.py` — lines 171-173, 182-184 (`url`, `thumbnail_path`, `playback_path`, `metadata_path`)

**Manifest and gallery data URLs** (1 file):
- `src/gengallery/services/gallery_processor.py` — line 250 (`f"/galleries/{gallery_id}/{variant_name}/..."`), line 322 (`manifest_path`), line 423 (`get_variant_url` default fallback)

**Jinja templates** (10 files, every root-absolute `href`, `src`, `action`):
- `src/gengallery/assets/templates/index.html.jinja` — 9 root-absolute paths
- `src/gengallery/assets/templates/gallery.html.jinja` — 12 root-absolute paths
- `src/gengallery/assets/templates/image.html.jinja` — 7 root-absolute paths
- `src/gengallery/assets/templates/video.html.jinja` — 6 root-absolute paths
- `src/gengallery/assets/templates/encrypted_gallery.html.jinja` — 10 root-absolute paths
- `src/gengallery/assets/templates/encrypted_image.html.jinja` — 7 root-absolute paths
- `src/gengallery/assets/templates/encrypted_video.html.jinja` — 6 root-absolute paths
- `src/gengallery/assets/templates/gallery_login.html.jinja` — 3 root-absolute paths
- `src/gengallery/assets/templates/404.html.jinja` — 3 root-absolute paths
- `src/gengallery/assets/templates/person_pills.html.jinja` — 1 root-absolute path

**Generator context** (1 file):
- `src/gengallery/services/generator.py` — `create_jinja_environment()` to add `base_path` global; `generate_gallery_listing_pages()` context; `generate_gallery_pages()` context; `generate_404_page()` context

**Serve handler** (1 file):
- `src/gengallery/services/serve.py` — add `PrefixedHTTPRequestHandler` class, conditionally select it in `run_serve()`
- `src/gengallery/commands/serve.py` — pass `base_path` from config to `run_serve()`, update banner message

**Config loading and validation** (2 files):
- `src/gengallery/services/image_processor.py` — `config` dict already mutable, pick up `base_path`
- `src/gengallery/assets/scaffold/` — init scaffold `config.yaml` template may need `# base_path: ""` comment

**Test files** requiring updates:
- `tests/python/test_gallery_paths.py` — add tests for `url()` helper
- `tests/python/test_cli_path_semantics.py` — verify `base_path` loads from config
- New test file: `tests/python/test_base_path.py` — verify metadata URLs are prefixed, template context includes `base_path`, serve handler, and all path surfaces are covered

### Dependencies & Integration

- Zero external dependencies — pure Python/stdlib + Jinja2 (already in project)
- The Hexate handoff document (`~/services/hexate/docs/GENGALLERY_BASE_PATH_HANDOFF.md`) documents the consumer side — after upstream ships, Hexate sets `base_path: "/gallery"` in its overlay config and rebuilds
- Default `""` preserves standalone deploys at `gallery.nil42.com` and the `serve` command

## Acceptance Criteria

- [ ] With `base_path: ""` (default), all generated HTML is byte-identical to current output — regression-freedom verified by `diff -r`
- [ ] With `base_path: "/gallery"`, all generated HTML URLs are correctly prefixed: `/gallery/galleries/...`, `/gallery/css/...`, `/gallery/` (home), `/gallery/{tag_hash}.html`
- [ ] With `base_path: "/gallery"`, clicking `gallery.index.html` → image detail page → back to gallery → home works with zero 404s
- [ ] CSS loads correctly under prefix (verified via browser dev tools or curl)
- [ ] All 10 templates produce valid URLs with and without prefix
- [ ] Encrypted galleries (manifest JSON + JS decryption) work with prefix — manifest URL in `<meta>` tag matches actual manifest path
- [ ] Video playback and thumbnail URLs are correctly prefixed
- [ ] Tag pages and `person_pills.html` links are correctly prefixed

## Implementation Tasks

- [ ] Add `url()` helper module at `src/gengallery/services/urls.py` with `set_base_path()`, `base_path()`, `url()`
- [ ] Load and normalize `base_path` from config into the global `config` dict
- [ ] Patch `image_processor.py`: wrap 5 metadata URL fields with `url()`
- [ ] Patch `video_processor.py`: wrap 4 metadata URL fields with `url()` (+ cover path from `check_video_outputs`)
- [ ] Patch `gallery_processor.py`: wrap `get_variant_url()` fallback, `write_manifest_file()` return, cover URLs
- [ ] Patch `generator.py`: add `base_path` to Jinja environment globals, pass into all template rendering contexts
- [ ] Patch all 10 `.jinja` templates: replace every root-absolute `href="/..."`, `src="/..."` with `{{ base_path }}/...`
- [ ] Handle `href="/"` edge case: use `{{ base_path + '/' if base_path else '/' }}` so home link is `/gallery/` (trailing slash for nginx location match)
- [ ] Add `PrefixedHTTPRequestHandler` to `services/serve.py` with base path stripping in `translate_path()`
- [ ] Wire `base_path` from config through `commands/serve.py` → `run_serve()`; update `run_serve` URL message
- [ ] Add tests for `url()` helper, default behavior, prefix behavior, and serve handler translate_path
- [ ] Verify regression with `diff -r` on a `base_path: ""` build vs current output
- [ ] Update spec handoff in `~/services/hexate/docs/GENGALLERY_BASE_PATH_HANDOFF.md` after implementation ships

## Risk Assessment

### Potential Issues
- **Double-slash paths**: `base_path: "/"` + template `/css/...` → `//css/...` (browser treats as protocol-relative URL, resolves incorrectly). Mitigation: normalize `base_path` at load time — strip trailing slash, treat `""` and `"/"` identically.
- **JSON manifest content**: `write_manifest_file()` embeds URLs in JSON that are consumed by client-side JS. These must match the browser-accessible URL with prefix. The `create_manifest_dict()` builds URLs from `get_variant_url()` which already uses `/galleries/...` format — must prefix consistently.
- **`serve` command (before fix)**: The local dev server with no `PrefixedHTTPRequestHandler` would produce broken URLs in the browser. **Fixed by** `PrefixedHTTPRequestHandler` subclass described above — `translate_path()` strips the prefix transparently.
- **Missed template paths**: Easy to miss a `href` in one of 10 templates. Mitigation: grep for `href="/`, `src="/`, `action="/` after patching and verify each one.

### Mitigation Strategies
- **Helper function in one place**: All prefix logic lives in `urls.py` — one import, one function to audit
- **Template audit pass**: After patching, run `grep -rn 'href="/\|src="/\|action="/' src/gengallery/assets/templates/` and verify every line is either patched or intentionally absolute
- **Regression baseline**: Build a gallery with `base_path: ""`, capture HTML output, then rebuild with same config after changes and `diff -r` the two trees
- **Hexate validation**: After implementation, apply the fix to the Hexate container config and run the acceptance test from the handoff doc
- **Serve handler test**: Unit test `PrefixedHTTPRequestHandler.translate_path()` with and without `base_path` to verify prefix stripping and the trailing-slash home link redirect

### Investigation Requirements
- Does `encrypted_video.html.jinja` exist? (Noted: it does. Fully reviewed.)
