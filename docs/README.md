# Gengallery

Version 1.0

## Create a static site as simply as possible.

Create folders under `galleries`, add images, create a gallery card.

Then run a single command to generate your site in `export/public_html`. Run the included server to demo locally on your browser.

The rest you do is your business.

## Getting Started

1. Copy `config.example.yaml` to `config.yaml` and make changes as desired.

2. Install Python dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```

3. Install Node.js and npm:
   - Windows: Download and install from [nodejs.org](https://nodejs.org/)
   - macOS: `brew install node`
   - Linux: Use your package manager (e.g., `apt install nodejs npm`)

4. Install Tailwind CSS dependencies:
   ```bash
   npm install
   ```

5. For SSH deployment, ensure rsync is installed:
   - Windows: Install via WSL or Cygwin
   - macOS: Included by default
   - Linux: `apt install rsync` or equivalent

## Usage

1. Create a folder in `galleries` (recommended format: YYYYMMDD), and add a `gallery.yaml`
2. Add your images and optional image metadata YAML files
3. Run `bin/refresh.py --all` to update entire site, or if run for the first time
4. Run `bin/refresh.py galleryname` to add/refresh that gallery
5. Run `bin/serve.py` to start a development server with live reload
6. It is safe to delete anything in `export` as long as you run `bin/refresh.py --all` afterward
7. Run `git pull` for updates and new features

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
- `unlisted`: Set to true to hide from listings (optional)

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
   - Always unlisted and never featured (featured tag ignored)
   - Requires password authentication
   - Server administrators cannot view image content, but HTML is clear text
   - Images decrypted in browser
   - Gallery is unlisted and tags are not indexed

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
- Security settings can be combined (except for encrypted galleries which override other settings)
- Featured status is ignored for encrypted galleries

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

The project supports two deployment methods: AWS (S3/CloudFront) and SSH/rsync.

### AWS Deployment

Configure AWS settings in `config.yaml`:
```yaml
aws:
  access_key_id: YOUR_ACCESS_KEY_ID
  secret_access_key: YOUR_SECRET_ACCESS_KEY
  region: YOUR_AWS_REGION
  s3:
    bucket_name: YOUR_BUCKET_NAME
  cloudfront:
    distribution_id: YOUR_DISTRIBUTION_ID  # Optional
```

Run `bin/deploy.py` to deploy via AWS. This will:
- Upload new and modified files to S3
- Remove files from S3 that no longer exist locally
- Automatically detect content types for files
- Invalidate CloudFront cache (if distribution_id is configured)

### SSH Deployment

Configure SSH settings in `config.yaml`:
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

Run `bin/deploy_ssh.py` to deploy via SSH/rsync. This will:
- Sync files using rsync to the remote server
- Execute configured post-sync commands (e.g., setting permissions)
- Support variable substitution in commands ({user}, {group}, {destination})

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

AWS:
- Ensure your AWS credentials have sufficient permissions
- Verify your S3 bucket exists and is accessible
- Check that your CloudFront distribution ID is correct if using CDN

SSH:
- Verify SSH connectivity to the remote server
- Ensure rsync is installed on both systems
- Check that the user has necessary permissions for post-sync commands

## Requirements

Core Dependencies:
- Python 3.8+
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
