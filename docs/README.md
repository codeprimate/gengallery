# Gengallery

Version 1.0

## Create a static site as simply as possible.

Create folders under `galleries`, add images, create a gallery card.

Then run a single command to generate your site in `export/public_html`. Run the included server to demo locally on your browser.

The rest you do is your business.

## Getting Started

The **gengallery** command is the supported entrypoint (console script from this package). After dependencies are installed, run it via `uv run gengallery …` or activate your environment and run `gengallery` directly.

1. **New project:** scaffold a directory (missing parents are created; existing `config.yaml`, `package.json`, `galleries/`, or `templates/` cause a **non-zero exit**—there is no `--force`):
   ```bash
   uv sync --extra dev
   uv run gengallery init /path/to/my-gallery-site
   ```
   `gengallery init` writes `package.json` and runs **`npm install`** in that directory so Tailwind is available for `gengallery update`. **Node.js and npm must be installed first** (see step 4).

   Then edit `config.yaml` and add content under `galleries/` as below.

2. **Existing project:** copy the example config template `config.yaml.example` to `config.yaml` if you do not already have one, and adjust paths and settings.

3. Install Python dependencies with uv:
   ```bash
   uv sync --extra dev
   ```

4. Install Node.js and npm (required before `gengallery init` or for manual `npm install` in an existing site):
   - Windows: Download and install from [nodejs.org](https://nodejs.org/)
   - macOS: `brew install node`
   - Linux: Use your package manager (e.g., `apt install nodejs npm`)

5. For SSH deployment, ensure rsync is installed:
   - Windows: Install via WSL or Cygwin
   - macOS: Included by default
   - Linux: `apt install rsync` or equivalent

If you add a project without using `gengallery init`, run **`npm install`** in the project root (same `package.json` layout as the scaffold) before `gengallery update`.

## Development Setup (uv)

This project uses `uv` as the Python dependency manager.

1. Ensure `uv` is installed:
   ```bash
   uv --version
   ```

2. Sync dependencies (including test tooling):
   ```bash
   uv sync --extra dev
   ```

3. Run Python tests in the uv-managed environment (or `make test`):
   ```bash
   uv run pytest tests/python -m "not integration"
   ```
   Expensive integration tests (optional): `make test-integration` (sets `GENGALLERY_INTEGRATION=1`).

4. Run JS parity tests:
   ```bash
   node --test tests/js/crypto-vectors.test.mjs
   ```

5. Run both suites via npm scripts:
   ```bash
   npm run test:vectors
   ```

## Usage

### Path argument (all commands)

For `gengallery init`, `update`, `serve`, and `push ssh`, the optional project path works as follows:

- **Omitted** — project root is the **current working directory**.
- **Relative** — resolved against the current working directory (e.g. `gengallery update ./my-site`).
- **Absolute** — used as-is after normalization (symlinks resolved).

Examples (from inside the project directory):

```bash
gengallery update
gengallery serve
gengallery push ssh
```

Or with an explicit path:

```bash
gengallery update /path/to/site
gengallery serve ../other-site --port 8000
```

### Day-to-day workflow

1. Create a folder in `galleries` (recommended format: YYYYMMDD), and add a `gallery.yaml`.
2. Add your images and optional image metadata YAML files.
3. **Videos (optional):** Install `ffmpeg` and `ffprobe` on your PATH. Put `.mp4`, `.mov`, or `.m4v` files in the gallery folder next to your photos (same directory as `gallery.yaml`). They are transcoded to H.264/AAC (max **120s** trim, **3 Mbps** at 720p-tier height / **5 Mbps** at 1080p-tier) plus a grid thumbnail; playback files are written under `export/.../galleries/<id>/video/`. Optional sidecar YAML next to each clip (e.g. `clip.yaml`) can set `title`, `caption`, and `tags`, same idea as photos.
4. Run **`gengallery update`** from the project root (or pass `[path]`). This runs the full pipeline—images, **face detection and labeling**, videos, gallery aggregation, and site generation—equivalent to the former `refresh.py` with **`--all`**. Per-gallery-only refresh is **not** exposed as a CLI subcommand in this release.
5. Run **`gengallery serve`** to preview the built site. The server binds to **127.0.0.1** only, default port **8000** (override with `--port`). There is **no** live reload; it is Python’s `SimpleHTTPRequestHandler` serving `output_path/public_html`.
6. It is safe to delete content under `export` as long as you run **`gengallery update`** afterward to rebuild.
7. Run `git pull` for updates and new features.

### Migration from legacy `bin/*.py` scripts

Older docs and automation may have called `bin/refresh.py`, `bin/serve.py`, `bin/deploy_ssh.py`, etc. Those entrypoints have been **removed**. Use:

| Former | Replacement |
|--------|-------------|
| `bin/refresh.py` (full build) | `gengallery update` |
| `bin/serve.py` | `gengallery serve` |
| `bin/deploy_ssh.py` | `gengallery push ssh` |

There is **no** `gengallery push aws` in this release (AWS deploy is out of scope for the CLI; the historical script was `bin/deploy_aws.py`).

## Gallery Configuration

Each gallery should have a `gallery.yaml` file with the following options:
- `title`: Gallery title
- `date`: Date of the gallery (YYYY-MM-DD format)
- `location`: Location of the photos (optional)
- `description`: Short description (optional)
- `content`: Extended markdown content (optional)
- `tags`: List of tags (include 'featured' to show on homepage)
- `cover`: Filename of the cover image (optional, first image used if not specified)
- `encrypted`: Enable encryption for private galleries (optional)
- `password`: Password protection for the gallery (optional)
- `unlisted`: Set to true to hide from listings (optional). For encrypted galleries, omitting this key (or setting true) keeps the gallery unlisted; set to **false** explicitly if you want a featured encrypted gallery on the home page.

## Gallery Types and Security

The system supports several types of galleries with different visibility and security levels:

1. **Encrypted Galleries** (Maximum Security)
   ```yaml
   title: "Private Collection"
   encrypted: true
   password: "secret123"
   ```
   - Uses AES-CBC encryption with client-side decryption
   - All images are encrypted before transfer to server
   - **Default:** unlisted (hidden from the home page and tag listings). To show on the home page, add the `featured` tag and set `unlisted: false` explicitly in YAML.
   - On listings, encrypted galleries use a lock placeholder image (no cover preview), no description, and no tag links; other tags in YAML do not create tag pages or Browse entries.
   - Requires password authentication
   - Server administrators cannot view image content, but HTML is clear text
   - Images decrypted in browser

2. **Password Protected Galleries**
   ```yaml
   title: "Wedding Photos"
   password: "Smith2024"
   ```
   - Requires authentication before access
   - Content stored unencrypted on server
   - Uses SHA-256 hashing for gallery URLs
   - Listed by default, can be combined with unlisted/featured status
   - Login persists through browser session

3. **Unlisted Galleries**
   ```yaml
   title: "Client Preview"
   unlisted: true
   ```
   - Hidden from navigation and listings
   - Accessible via direct URL
   - Basic privacy through obscurity
   - Cannot be combined with featured status

4. **Standard/Featured Galleries**
   ```yaml
   title: "Summer Vacation"
   tags:
     - featured
   ```
   - Fully public content
   - Visible in navigation and listings
   - No access restrictions

**Additional Security Notes:**
- All gallery and image URLs use SHA-256 hashes for added obscurity
- Password-protected galleries show a login page before redirecting to the hashed URL
- Encrypted galleries default to unlisted; listing visibility is opt-in via explicit `unlisted: false` plus the `featured` tag

## Image Metadata

Each image can have an optional YAML metadata file (same name as image with .yaml extension):
- `title`: Image title (defaults to filename if not specified)
- `caption`: Image caption (optional)
- `tags`: List of tags for the image (optional)

When face labeling is in use, the pipeline **manages** `person:{slug}` tags in sidecar YAML automatically (see [Face detection and identity labeling](#face-detection-and-identity-labeling)). Other tags you set by hand are left unchanged.

The system will automatically extract and store EXIF data including:
- Camera make and model
- Lens information
- Exposure settings
- GPS coordinates (if available)
- Date and time

See `docs/example_gallery/waves.yaml` for an example.

## Face Detection and Identity Labeling

GenGallery detects faces during **`gengallery update`**, lets you name people from the CLI, and propagates those names across your photo library. There is no person-browse page in the site yet—the payoff today is automatic **`person:alice`** tags on image sidecars and local metadata you can search or build on later.

### Before you start

1. Run from your **project root** (where `config.yaml` and `galleries/` live).
2. Run **`gengallery update`** at least once so faces are detected. Labeling commands read detection data from the last update.
3. On first use, face models download to **`~/.cache/gengallery/models/`**. Normal `uv sync` is enough—no extra install step.

### Concepts (30 seconds)

| Term | Meaning |
|------|---------|
| **Identity / slug** | A person’s stable ID, e.g. `alice`. Lowercase letters, digits, hyphens; must start with a letter. |
| **Positive** | “This face **is** Alice.” You set these with `faces assign`. |
| **Negative** | “This face is **not** Alice.” You set these with `faces reject` to stop false matches. |
| **Propagated** | A match inferred from your positives. Recomputed every `update`. |
| **Face index** | `0`, `1`, `2`… when an image has multiple people. Use `faces show` to see which is which. |

Your positive labels are stored in **`galleries/identities.yaml`**. The CLI creates and edits this file. Commit it if you want names in git.

---

### Tutorial: name someone in your library

Assume gallery folder `galleries/20240715/` with `portrait.jpg` (one person) and `party.jpg` (several people).

**Step 1 — Detect faces**

```bash
gengallery update
```

**Step 2 — Pick a clear example and assign a name**

Single-face photo (no `--face` needed):

```bash
gengallery faces assign alice 20240715/portrait.jpg
```

This creates `galleries/identities.yaml` if needed and records Alice’s face as a positive example.

**Step 3 — Propagate across the library**

```bash
gengallery update
```

The face stage matches similar faces to Alice and writes **`person:alice`** into sidecar YAML (e.g. `20240715/wedding.yaml`) for every image where she appears.

**Step 4 — Check a crowded photo**

```bash
gengallery faces show 20240715/party.jpg
```

Example output:

```
  20240715/party.jpg  3 face(s)
    face  0  bbox=[0.120, 0.080, 0.220, 0.280]  conf=0.981  identity=alice  prov=propagated
    face  1  bbox=[0.450, 0.100, 0.180, 0.240]  conf=0.972  identity=unassigned  prov=unassigned
    face  2  bbox=[0.720, 0.090, 0.190, 0.250]  conf=0.965  identity=unassigned  prov=unassigned
    Crops written:
      galleries/_metadata/crops/20240715/party_0.jpg
      galleries/_metadata/crops/20240715/party_1.jpg
      galleries/_metadata/crops/20240715/party_2.jpg
```

Open the crop JPEGs to see who is face 0, 1, 2. Assign another person:

```bash
gengallery faces assign bob 20240715/party.jpg --face 1
gengallery update
```

**Step 5 — Fix a wrong match**

If Alice was propagated to the wrong face in a group shot:

```bash
gengallery faces reject alice 20240715/party.jpg --face 2
gengallery update
```

That face will never be assigned to `alice` again. Add a positive for the correct person if needed:

```bash
gengallery faces assign bob 20240715/party.jpg --face 2
gengallery update
```

---

### Command recipes

#### `faces show` — see faces before you label

Always run this when an image might have **more than one** person:

```bash
gengallery faces show 20240715/party.jpg
gengallery faces show 20240715/a.jpg 20240715/b.jpg   # multiple images
```

Writes crop thumbnails to **`galleries/_metadata/crops/{gallery_id}/`**. Face indices in the terminal match `--face N` on other commands.

If you see **“No face detection data … Run gengallery update first”**, run `update` and try again.

#### `faces assign` — “this face is `<slug>`”

```bash
# New identity (slug created automatically; display name title-cased from slug)
gengallery faces assign alice 20240715/portrait.jpg

# Multi-face image — --face is required
gengallery faces assign bob 20240715/party.jpg --face 1

# Several positives at once (same identity)
gengallery faces assign alice 20240715/a.jpg 20240715/b.jpg --face 0
```

Rules:

- **One face** in the image → omit `--face`.
- **Multiple faces** → `--face N` is **required** or the command errors. Run `faces show` first.
- **No faces detected** → error. The photo may be too small, blurred, or below confidence thresholds.

After every assign, run **`gengallery update`** to propagate and refresh auto-tags.

#### `faces unassign` — remove a positive you added by mistake

```bash
gengallery faces unassign 20240715/portrait.jpg
gengallery faces unassign 20240715/party.jpg --face 0
gengallery update
```

Removes the positive from `identities.yaml` and clears propagated assignment for that face on the next update. Does not delete the identity slug if other positives remain.

#### `faces reject` — “this face is NOT `<slug>`”

Use when propagation keeps matching the wrong person (twins, similar-looking relatives, etc.):

```bash
gengallery faces reject alice 20240715/group.jpg --face 2
gengallery update
```

Negatives are stored in `identities.yaml` and block future propagation to that identity for that face only.

#### `faces merge` — combine two identities

If you accidentally created `alice-smith` and `alice`:

```bash
gengallery faces merge alice-smith alice
gengallery update
```

All positives and negatives from the source move into the target; the source slug is removed.

#### `faces propagate` — preview or rerun matching without a full rebuild

```bash
gengallery faces propagate --dry-run
gengallery faces propagate --dry-run --identity alice
gengallery faces propagate                    # apply changes
```

Useful when tuning **`faces.match_threshold`** in `config.yaml`. Lower = more matches (more false positives). Higher = stricter.

#### `faces recluster` — regroup unknown faces

```bash
gengallery faces recluster
gengallery update
```

Rebuilds anonymous **`id_unnamed_*`** clusters for faces with no named identity. Named assignments are untouched.

---

### What `gengallery update` does for faces

Each update runs the face stage automatically (after images, before videos):

1. Detect faces and compute embeddings (skipped for unchanged images when possible).
2. Apply positives and negatives from **`galleries/identities.yaml`**.
3. Propagate named identities to similar unlabeled faces.
4. Cluster remaining unknowns into anonymous groups.
5. Write **`person:{slug}`** tags into image sidecar YAML for **named** identities only.

Example sidecar after update (`20240715/wedding.yaml`):

```yaml
tags:
  - person:alice
  - person:bob
  - sunset
```

Tags you set manually (like `sunset`) are kept. Only **`person:*`** tags are rewritten each update.

---

### `identities.yaml` (optional to edit by hand)

The CLI maintains this file. You can read or edit it directly if you prefer:

```yaml
identities:
  alice:
    display_name: Alice
    positives:
      - gallery: "20240715"
        image: portrait.jpg
      - gallery: "20240715"
        image: party.jpg
        face: 0
    negatives:
      - gallery: "20240715"
        image: group.jpg
        face: 2
```

After hand-editing, run **`gengallery update`** to apply changes.

---

### Configuration

Optional `faces` section in `config.yaml`:

```yaml
faces:
  match_threshold: 0.55          # propagation: higher = fewer false positives
  cluster_threshold: 0.45        # anonymous recluster merge threshold
  min_face_size_px: 40           # ignore tiny detections
  min_detection_confidence: 0.50
  auto_tag_prefix: "person:"
  hdbscan_min_cluster_size: 2
```

If propagation is too aggressive, raise **`match_threshold`** (try `0.60`–`0.65`) and use **`faces propagate --dry-run`** to preview.

---

### Privacy and deployment

- Embeddings and crops live under **`galleries/_metadata/`**—sensitive; back up with your project.
- **`gengallery push ssh`** uploads **`export/public_html` only**—not `_metadata` or embeddings.
- Anonymous slugs (`id_unnamed_*`) are never auto-tagged; only named people get `person:*` tags.

Full design: [specs_faces.md](specs_faces.md).

## Deployment

### SSH / rsync (supported CLI)

Configure SSH settings in `config.yaml`. The key `ssh.post_sync_commands` must be a **non-empty** list of strings. `user`, `host`, `destination`, and `group` may be omitted; defaults match the previous `deploy_ssh.py` behavior.

```yaml
ssh:
  user: "admin"
  host: "gallery.example.com"
  destination: "/data/gallery/"
  group: "www-data"
  post_sync_commands:
    - "sudo chown -R {user}:{group} {destination}"
    - "sudo chmod -R go+rX {destination}"
```

From the project directory (or pass `[path]`):

```bash
gengallery push ssh
```

This will:

- Sync `output_path/public_html` to the remote `destination` using rsync over SSH
- Run each `post_sync_commands` entry after sync
- Substitute `{user}`, `{group}`, and `{destination}` in those commands

### AWS (S3 / CloudFront)

AWS deployment is **not** wired into the `gengallery` CLI in this release (`gengallery push aws` is unavailable). Configure AWS in `config.yaml` if you use external tooling or a future provider subcommand. Typical expectations when using boto3-based automation:

- Upload new and modified files to S3
- Remove remote objects that no longer exist locally
- Set content types appropriately
- Optionally invalidate a CloudFront distribution

### Prerequisites for Deployment

For AWS:
- AWS credentials with appropriate permissions for S3 and CloudFront
- An S3 bucket configured for static website hosting
- (Optional) A CloudFront distribution pointing to your S3 bucket

For SSH:
- SSH access to the destination server
- rsync installed on both local and remote systems
- Appropriate permissions to execute post-sync commands

### Troubleshooting

**SSH / `gengallery push ssh`**

- Verify SSH connectivity to the remote server
- Ensure rsync is installed on both systems
- Check that `post_sync_commands` is present and non-empty (otherwise the CLI exits with an error)
- Check that the remote user can run the configured post-sync commands

**AWS (external / future CLI)**

- Ensure credentials and bucket permissions are correct if you deploy outside the packaged CLI

## Requirements

Core Dependencies:
- Python 3.11+
- Node.js and npm (for Tailwind CSS)
- Pillow >= 9.0.0 (for image processing)
- exif >= 1.3.0 (for EXIF metadata handling)
- PyYAML >= 6.0.0 (for configuration files)
- rich >= 12.0.0 (for console output formatting)
- Jinja2 >= 3.0.0 (for template rendering)
- markdown >= 3.4.0 (for markdown processing)
- plum-py >= 0.8.0 (for binary data handling)
- onnxruntime >= 1.16.0, numpy >= 1.24.0, opencv-python-headless >= 4.8.0 (face detection and identity labeling; models download on first use)

Deployment Dependencies:
- boto3 >= 1.26.0 (for AWS S3/CloudFront deployment)
- botocore >= 1.29.0 (required by boto3)
- rsync (for SSH deployment)

Security:
- cryptography >= 37.0.0 (for encrypted galleries)

## Specifications

- [Core gallery generator](specs.md)
- [Encrypted galleries](specs_enc.md)
- [Face detection and identity labeling](specs_faces.md)

# Copyright

(c)2024-2025 codeprimate under MIT License
