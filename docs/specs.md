# Photo Gallery Generator Specifications

This document outlines the specifications for a static photo gallery generator using Python scripts, YAML for configuration and gallery information, and JSON for storing processed gallery and image data.

## Project Structure

```
.
├── bin/
│   ├── image_processor.py
│   ├── gallery_processor.py
│   └── generator.py
├── galleries/
│   └── YYYYMMDD/
│       ├── gallery.yml
│       └─ *.jpg
├── templates/
│   ├── index.html.jinja
│   ├── gallery.html.jinja
│   ├── image.html.jinja
│   ├── site.css
│   └── site.js
├── export/
│   ├── index.html (generated)
│   ├── galleries.json (generated)
│   ├── css/
│   │   └── site.css (copied)
│   ├── js/
│   │   └── site.js (copied)
│   └── galleries/
│       └── YYYYMMDD/
│           ├── index.html (generated)
│           ├── index.json (generated)
│           ├── *.html (generated image pages)
│           ├── cover/
│           │   └── *.jpg (processed)
│           ├── full/
│           │   └── *.jpg (processed)
│           ├── metadata/
│           │   └── *.json (generated)
│           └── thumbnail/
│               └── *.jpg (processed)
├── config.yml
└── README.md
```

## Configuration (config.yml)

```yaml
image_sizes:
  cover: 1024
  thumbnail: 300
  full: 3840
jpg_quality: 85
output_path: "./export"
source_path: "./galleries"
galleries_per_page: 999
images_per_gallery_page: 999
exif_fields:
  - DateTimeOriginal
  - LensModel
  - FocalLength
  - ExposureTime
  - FNumber
  - ISO
site_name: "My Photography Gallery"
author: "Your Name"
```

## Gallery Post File (post.yml)

```yaml
title: "Summer in the Mountains"
date: 2024-07-15
location: "Rocky Mountains, Colorado"
tags:
  - landscape
  - summer
  - mountains
description: "A collection of photographs taken during a week-long hiking trip in the Rocky Mountains."
content: |
  ## Journey Through the Rockies
  
  This gallery showcases the stunning beauty of the Rocky Mountains 
  during the height of summer. From sweeping vistas of snow-capped peaks 
  to close-ups of delicate alpine flowers, each image tells a story of 
  the raw, untamed wilderness.
  
  ### Highlights
  
  - Dawn at Eagle's Peak
  - The hidden waterfall of Whisper Valley
  - Sunset over the Continental Divide
  
  Throughout the week, we encountered diverse weather conditions, from 
  brilliant sunshine to dramatic afternoon thunderstorms, each offering 
  unique photographic opportunities.
  
  I hope these images inspire you to explore and appreciate the natural 
  wonders that surround us.
cover: "sunset_panorama.jpg"
```

## Script Functionalities

### image_processor.py
- Reads configuration from config.yml
- Processes each image in source galleries:
  - Extracts EXIF data and GPS coordinates
  - Resizes images for different uses (full-size, thumbnail, cover)
  - Creates a metadata dictionary for each image
  - Saves resized images in appropriate directories
  - Saves a JSON metadata file for each image in the metadata directory

### gallery_processor.py
- Reads configuration from config.yml
- Processes each gallery:
  - Reads gallery.yml for gallery information
  - Processes cover image metadata
  - Loads and processes metadata for all images in the gallery
  - Sorts images by date taken (if available in EXIF data)
- Sorts galleries by date, most recent first
- Generates a single galleries.json file with all gallery and image information

### generator.py
- Reads configuration from config.yml
- Loads processed gallery data from galleries.json
- Generates HTML pages using Jinja2 templates:
  - Root index.html (list of all galleries)
  - Individual gallery index.html pages
  - Individual image pages
- Copies static files (CSS, JS) to the export directory

## Data Structures

### Image Metadata (JSON)
```json
{
 "filename": "mountain_vista.jpg",
 "path": "/galleries/20240715/full/mountain_vista.jpg",
 "thumbnail_path": "/galleries/20240715/thumbnail/mountain_vista.jpg",
 "cover_path": "/galleries/20240715/cover/mountain_vista.jpg",
 "title": "Mountain Vista",
 "caption": "A breathtaking view of the Rocky Mountains at sunrise",
 "lat": 40.3772,
 "lon": -105.5217,
 "exif": {
   "DateTimeOriginal": "2024:07:15 05:30:00",
   "LensModel": "RF24-105mm F4 L IS USM",
   "FocalLength": 28,
   "ExposureTime": "1/125",
   "FNumber": 8,
   "ISO": 100
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
2. User runs image_processor.py to process images and generate metadata
3. User runs gallery_processor.py to generate galleries.json
4. User runs generator.py to create HTML pages and copy static files
5. Resulting static site is output to the export directory

This system is designed to be flexible, easily extensible, and to generate a clean, responsive photo gallery website.