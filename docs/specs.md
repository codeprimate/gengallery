# Photo Gallery Generator Specifications

This document outlines the specifications for a static photo gallery generator using Python scripts, YAML for configuration and gallery information, and JSON for storing processed gallery and image data.

## Project Structure

```
.
├── bin/
│   ├── image_processor.py
│   ├── gallery_processor.py
│   ├── generator.py
│   ├── deploy_ssh.py
│   ├── deploy_aws.py
│   ├── refresh.py
│   ├── serve.py
│   └── deploy_ssh.py
├── galleries/
│   └── YYYYMMDD/
│       ├── gallery.yaml
│       ├── *.yaml (optional image metadata)
│       └── *.jpg
├── templates/
│   ├── 404.html.jinja
│   ├── gallery.html.jinja
│   ├── gallery_login.html.jinja
│   ├── encrypted_gallery.html.jinja
│   ├── image.html.jinja
│   ├── encrypted_image.html.jinja
│   ├── index.html.jinja
│   ├── site.css
│   ├── site.js
│   ├── favicon.ico
│   ├── robots.txt
│   └── tailwind/
│       ├── tailwind.config.js
│       ├── tailwind_input.css
│       └── tailwind.css (generated)
├── export/
│   ├── metadata/
│   │   ├── galleries.json
│   │   └── YYYYMMDD/
│   │       ├── index.json
│   │       └── *.json
│   └── public_html/
│       ├── index.html
│       ├── 404.html
│       ├── *.html (tag pages)
│       ├── favicon.ico
│       ├── robots.txt
│       ├── css/
│       │   ├── site.css
│       │   └── tailwind.css
│       ├── js/
│       │   └── site.js
│       └── galleries/
│           └── YYYYMMDD/
│               ├── index.html
│               ├── *.html (image pages)
│               ├── cover/
│               │   └── *.jpg
│               ├── full/
│               │   └── *.jpg
│               └── thumbnail/
│                   └── *.jpg
├── config.yaml
└── README.md
```

## Configuration (config.yaml)

```yaml
# Image processing settings
image_sizes:
  cover: 1024
  thumbnail: 300
  full: 3840
jpg_quality: 85

# Path configuration
output_path: "./export"
source_path: "./galleries"

# Site settings
site_name: "My Photography Gallery"
author: "Your Name"

# SSH deployment settings (optional)
ssh:
  user: "admin"
  host: "gallery.nil42.com"
  destination: "/data/gallery/"
  group: "www-data"
  post_sync_commands:
    - "chown -R {user}:{group} {destination}"
    - "chmod -R 755 {destination}"
```

## Gallery Configuration (gallery.yaml)

```yaml
title: "Summer in the Mountains"
date: 2024-07-15
location: "Rocky Mountains, Colorado"
tags:
  - landscape
  - summer
  - mountains
  - featured
description: "A collection of photographs taken during a week-long hiking trip."
content: |
  ## Journey Through the Rockies
  
  This gallery showcases the stunning beauty of the Rocky Mountains 
  during the height of summer.
cover: "sunset_panorama.jpg"
unlisted: false  # Optional: hide from main listing
encrypted: false # Optional: enable encryption
password: ""     # Optional: for password protection
```

## Featured Galleries

Galleries can be marked as featured by adding the `featured` tag to the gallery's tags list. Featured galleries are displayed prominently on the home page in a dedicated section while still respecting `unlisted` and `encrypted` settings.

Example featured gallery configuration:
```yaml
title: "Best of 2024"
tags:
  - featured
  - landscape
cover: "best_shot.jpg"
# ... other configuration ...
```

## Script Functionalities

### image_processor.py
- Reads configuration from config.yaml
- Processes each image in source galleries:
  - Generates unique deterministic image IDs
  - Extracts EXIF data including camera settings
  - Creates multiple sized versions of images
  - Supports optional encryption for private galleries
  - Handles image rotation based on EXIF
  - Reads additional metadata from .yaml files
  - Saves processed images and metadata
- Provides rich console output with progress tracking
- Exit codes:
  - 0: Success
  - 1: No arguments provided
  - 2: No galleries found
  - 3: Processing errors occurred
  - 130: Keyboard interrupt

### gallery_processor.py
- Reads configuration from config.yaml
- Processes each gallery:
  - Reads gallery.yaml for configuration
  - Processes cover image metadata
  - Loads and processes all image metadata
  - Handles encrypted and password-protected galleries
  - Cleans up metadata for missing images
- Generates consolidated galleries.json
- Provides detailed console output

### generator.py
- Reads configuration and processed gallery data
- Generates HTML pages using Jinja2 templates:
  - Main index page (tag-based navigation)
  - Individual tag listing pages
  - Gallery index pages (with optional login)
  - Individual image pages
  - 404 error page
- Handles encrypted and password-protected galleries
- Generates Tailwind CSS
- Copies static assets
- Provides build summary with statistics

### deploy_ssh.py
- Deploys generated site via SSH/rsync
- Configurable host, user, and destination
- Runs post-sync commands (permissions, etc.)
- Uses SSH configuration from config.yaml

### deploy_aws.py
- Deploys generated site to AWS S3/CloudFront
- Configurable bucket and distribution settings
- Handles CloudFront cache invalidation
- Uses AWS credentials from environment/config

### refresh.py
- Convenience script to rebuild the entire site
- Runs the processing pipeline in sequence:
  1. Process images
  2. Process galleries
  3. Generate site
  4. Deploy (optional)
- Provides consolidated output of all stages

### serve.py
- Local development server for testing
- Serves the generated site from public_html directory
- Supports live reload for development
- Configurable port and host settings

## Data Structures

### Image Metadata (JSON)
```json
{
  "id": "a1b2c3d4e5f6",
  "filename": "mountain_vista.jpg",
  "url": "/galleries/20240715/a1b2c3d4e5f6.html",
  "path": "/galleries/20240715/full/a1b2c3d4e5f6.jpg",
  "thumbnail_path": "/galleries/20240715/thumbnail/a1b2c3d4e5f6.jpg",
  "cover_path": "/galleries/20240715/cover/a1b2c3d4e5f6.jpg",
  "title": "Mountain Vista",
  "caption": "A breathtaking view of the Rocky Mountains at sunrise",
  "tags": ["landscape", "mountains", "sunrise"],
  "lat": 40.3772,
  "lon": -105.5217,
  "exif": {
    "DateTimeOriginal": "2024:07:15 05:30:00",
    "Make": "Canon",
    "Model": "EOS R5",
    "LensModel": "RF24-105mm F4 L IS USM",
    "FocalLength": "28.0 mm",
    "ExposureTime": "1/125",
    "FNumber": "f/8.0",
    "ISO": 100,
    "ExposureCompensation": "0.0 EV",
    "MeteringMode": "PATTERN",
    "ExposureProgram": "MANUAL"
  }
}
```

### galleries.json Structure
```json
{
  "last_updated": "2024-08-24T12:00:00Z",
  "galleries": [
    {
      "id": "20240715",
      "title": "Summer in the Mountains",
      "date": "2024-07-15",
      "location": "Rocky Mountains, Colorado",
      "description": "A collection of photographs taken during a week-long hiking trip in the Rocky Mountains.",
      "tags": ["landscape", "summer", "mountains"],
      "cover": {
        "filename": "sunset_panorama.jpg",
        "title": "Sunset Panorama",
        "caption": "",
        "path": "/galleries/20240715/cover/sunset_panorama.jpg",
        "thumbnail_path": "/galleries/20240715/thumbnail/sunset_panorama.jpg"
      },
      "images": [
        // Array of image metadata objects
      ],
      "content": "## Journey Through the Rockies\n\nThis gallery showcases the stunning beauty of the Rocky Mountains during the height of summer. ..."
    }
  ]
}
```

## HTML Templates

### index.html.jinja
- Displays a list of all galleries
- Each gallery is represented by its cover image, title, date, and description
- Links to individual gallery pages

### gallery.html.jinja
- Displays gallery information (title, date, description, tags)
- Shows gallery cover image
- Presents a grid of image thumbnails
- Thumbnails link to full-size images
- Image titles link to individual image pages

### image.html.jinja
- Displays a centered cover image (linked to full-size image)
- Shows image title, filename, and caption (if available)
- Presents EXIF data in a grid layout
- Includes a link to view the image location on Google Maps (if GPS data is available)
- Provides navigation back to the gallery page

## Workflow
1. User populates source/galleries with new galleries and images
2. For development:
   - Run `serve.py` to start local development server
   - Make changes and preview in browser
3. For production:
   - Run `refresh.py` to rebuild entire site
   - Optionally specify deployment target (SSH/AWS)
4. Alternatively, run individual scripts as needed:
   - `image_processor.py` to process new images
   - `gallery_processor.py` to update gallery metadata
   - `generator.py` to rebuild HTML/CSS
   - `deploy_ssh.py` or `deploy_aws.py` to publish

This system is designed to be flexible, easily extensible, and to generate a clean, responsive photo gallery website.

## Gallery Security and Visibility

Galleries support several visibility and security options:

1. **Standard**: Public galleries visible in all navigation
2. **Featured**: Marked with `featured` tag for homepage prominence
3. **Unlisted**: Hidden from navigation but accessible via direct URL
4. **Password Protected**: Requires authentication to view content
5. **Encrypted**: Client-side AES-CBC encryption with password protection

### Gallery Types

1. **Standard Galleries**
   - Publicly visible and listed in main navigation
   - Accessible via direct URL
   - Included in tag listings and RSS feeds
   - Allows search engine indexing
   - Example:
   ```yaml
   title: "Summer Vacation"
   date: 2024-07-15
   tags:
     - travel
     - summer
   ```

2. **Featured Galleries**
   - Marked with the `featured` tag
   - Displayed prominently on home page
   - Inherits visibility rules from other settings (standard/unlisted/etc)
   - Follows same security and access rules as base type
   - Example:
   ```yaml
   title: "Best of 2024"
   tags:
     - featured
     - landscape
   ```

3. **Unlisted Galleries**
   - Hidden from main navigation, tag listings, and RSS feeds
   - Accessible only via direct URL
   - Blocked from search engine indexing via robots.txt
   - Useful for work-in-progress or private sharing
   - Example:
   ```yaml
   title: "Client Preview"
   unlisted: true
   tags:
     - client
     - wedding
   ```

4. **Password Protected Galleries**
   - Requires password authentication to view content
   - Listed in main index (unless also marked unlisted)
   - Uses SHA-256 hashing for private gallery ID
   - Content stored unencrypted but requires authentication
   - Login state stored in browser session storage
   - URL structure: `/galleries/YYYYMMDD/{private_gallery_id}.html`
   - Search engines can only index login page
   - Example:
   ```yaml
   title: "Wedding Photos"
   password: "Smith2024"
   tags:
     - wedding
     - private
   ```

5. **Encrypted Galleries**
   - Uses client-side AES-CBC encryption with PBKDF2 key derivation
   - All images and metadata encrypted
   - Requires password for client-side decryption
   - Automatically unlisted (hidden from all listings)
   - No server-side decryption capability
   - Deterministic IV generation for reproducible encryption
   - Blocked from search engine indexing
   - Example:
   ```yaml
   title: "Private Collection"
   encrypted: true
   password: "secret123"
   tags:
     - private
   ```

### Security Implementation

#### Password Protection
- Uses SHA-256 hashing to generate private gallery ID
- Gallery content stored unencrypted but requires authentication
- URL structure: `/galleries/YYYYMMDD/{private_gallery_id}.html`
- Login state stored in browser session storage

#### Encryption
- AES-CBC encryption with PBKDF2 key derivation
- All images decrypted client-side
- Deterministic IV generation for reproducible encryption
- No server-side decryption capability
- URL structure matches password protection

### Visibility Rules

1. **Standard Galleries**
   - Listed in: Main index, tag pages, RSS feeds
   - Accessible: Public URLs
   - Search indexing: Allowed

2. **Featured Galleries**
   - Additional listing: Home page featured section
   - Otherwise follows standard or specified visibility

3. **Unlisted Galleries**
   - Listed in: Nothing
   - Accessible: Direct URLs only
   - Search indexing: Blocked via robots.txt

4. **Password Protected**
   - Listed in: Main index (if not unlisted)
   - Accessible: After password entry
   - Search indexing: Login page only

5. **Encrypted**
   - Always unlisted
   - Listed in: Nothing
   - Accessible: With password for decryption
   - Search indexing: Blocked