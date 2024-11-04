# Gengallery

Version 0.1

## Create a static site as simply as possible.

Create folders under `galleries`, add images, create a gallery card.

Then run a single command to generate your site in `export`. Run the included server to demo locally on your browser.

The rest you do is your business.

## Getting Started

1. Copy `config.example.yaml` to `config.yaml` and make changes as desired.
2. Run `pip install -r requirements.txt`
3. Install Node.js and npm (required for Tailwind CSS processing)
4. Run `npm install` to install Tailwind CSS dependencies

## Usage

1. Create a folder in `galleries`, and add a `gallery.yaml` (See the example gallery in `docs/example_gallery`)
2. There are optional caption files for images (see example gallery in `docs/example_gallery`).
3. Run `bin/refresh.py --all` to update entire site, or if run for the first time
4. Run `bin/refresh.py galleryname` to add/refresh that gallery
5. Run `bin/serve.py` to start a webserver at http://localhost:8000
6. It is safe to delete anything in `exports` as long as you run `bin/refresh.py --all` afterward
7. Run `git pull` for updates and new features

## Gallery Configuration

Each gallery should have a `gallery.yaml` file with the following options:
- `title`: Gallery title
- `date`: Date of the gallery (YYYY-MM-DD format)
- `location`: Location of the photos (optional)
- `description`: Short description (optional)
- `tags`: List of tags (include 'featured' to show on homepage)
- `cover`: Filename of the cover image (optional, first image used if not specified)
- `password`: Password protection for the gallery (optional)
- `unlisted`: Set to true to hide from listings (optional)

See `docs/example_gallery/gallery.yaml` for a complete example:

## Image Metadata

Each image can have an optional YAML metadata file (same name as image with .yaml extension):
- `title`: Image title (defaults to filename if not specified)
- `caption`: Image caption (optional)
- `tags`: List of tags for the image (optional)

See `docs/example_gallery/waves.yaml` for an example:

## Deployment

The project includes AWS deployment capabilities through S3 and CloudFront:

1. Configure AWS settings in `config.yaml`:
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

2. Run `bin/deploy.py` to deploy your site. The deployment process will:
   - Upload new and modified files to S3
   - Remove files from S3 that no longer exist locally
   - Automatically detect content types for files
   - Invalidate CloudFront cache (if distribution_id is configured)

The deployment script includes smart file syncing that only uploads changed files, making deployments faster and more efficient.

### Prerequisites for Deployment
- AWS credentials with appropriate permissions for S3 and CloudFront
- An S3 bucket configured for static website hosting
- (Optional) A CloudFront distribution pointing to your S3 bucket

### Troubleshooting
- Ensure your AWS credentials have sufficient permissions
- Verify your S3 bucket exists and is accessible
- Check that your CloudFront distribution ID is correct if using CDN

## Requirements

- Python 3.8+
- Node.js and npm (for Tailwind CSS)
- PIL/Pillow
- PyYAML
- Jinja2
- Python Markdown
- boto3 (for AWS deployment)
- exif

# Copyright

(c)2024 codeprimate under MIT License
