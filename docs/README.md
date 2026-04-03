# Gengallery

Version 1.0

## Create a static site as simply as possible.

Create folders under `galleries`, add images, create a gallery card.

Then run a single command to generate your site in `export/public_html`. Run the included server to demo locally on your browser.

The rest you do is your business.

## Getting Started

The **gengallery** command is the supported entrypoint (console script from this package). After dependencies are installed, run it via `uv run gengallery …` or activate your environment and run `gengallery` directly.

1. **New project:** scaffold a directory (missing parents are created; existing `config.yaml`, `galleries/`, or `templates/` cause a **non-zero exit**—there is no `--force`):
   ```bash
   uv sync --extra dev
   uv run gengallery init /path/to/my-gallery-site
   ```
   Then edit `config.yaml` and add content under `galleries/` as below.

2. **Existing project:** copy `config.example.yaml` to `config.yaml` if you do not already have one, and adjust paths and settings.

3. Install Python dependencies with uv:
   ```bash
   uv sync --extra dev
   ```

4. Install Node.js and npm:
   - Windows: Download and install from [nodejs.org](https://nodejs.org/)
   - macOS: `brew install node`
   - Linux: Use your package manager (e.g., `apt install nodejs npm`)

5. Install Tailwind CSS dependencies:
   ```bash
   npm install
   ```

6. For SSH deployment, ensure rsync is installed:
   - Windows: Install via WSL or Cygwin
   - macOS: Included by default
   - Linux: `apt install rsync` or equivalent

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
4. Run **`gengallery update`** from the project root (or pass `[path]`). This runs the full pipeline—images, videos, gallery aggregation, and site generation—equivalent to the former `refresh.py` with **`--all`**. Per-gallery-only refresh is **not** exposed as a CLI subcommand in this release.
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

The system will automatically extract and store EXIF data including:
- Camera make and model
- Lens information
- Exposure settings
- GPS coordinates (if available)
- Date and time

See `docs/example_gallery/waves.yaml` for an example:

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

Deployment Dependencies:
- boto3 >= 1.26.0 (for AWS S3/CloudFront deployment)
- botocore >= 1.29.0 (required by boto3)
- rsync (for SSH deployment)

Security:
- cryptography >= 37.0.0 (for encrypted galleries)

# Copyright

(c)2024-2025 codeprimate under MIT License
