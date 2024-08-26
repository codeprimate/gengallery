#!/usr/bin/env python

import os
import json
import yaml
from datetime import datetime

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

def process_gallery(gallery_path, output_path):
    # Load gallery.yaml
    with open(os.path.join(gallery_path, 'gallery.yaml'), 'r') as f:
        post_data = yaml.safe_load(f)

    # Initialize gallery data
    gallery_data = {
        "id": os.path.basename(gallery_path),
        "last_updated": datetime.now().isoformat(),
        "title": post_data.get('title', ''),
        "date": post_data.get('date', '').isoformat(),
        "location": post_data.get('location', ''),
        "description": post_data.get('description', ''),
        "tags": post_data.get('tags', []),
        "content": post_data.get('content', ''),
        "images": []
    }

    # Process cover image
    cover_image_filename = post_data.get('cover', '')
    if cover_image_filename:
        cover_metadata_path = os.path.join(output_path, 'metadata', f"{os.path.splitext(cover_image_filename)[0]}.json")
        if os.path.exists(cover_metadata_path):
            with open(cover_metadata_path, 'r') as f:
                cover_metadata = json.load(f)
            gallery_data['cover'] = {
                "filename": cover_metadata['filename'],
                "title": cover_metadata['title'],
                "caption": cover_metadata['caption'],
                "path": cover_metadata['cover_path'],
                "thumbnail_path": cover_metadata['thumbnail_path'],
            }

    # Process all images
    metadata_dir = os.path.join(output_path, 'metadata')
    for metadata_file in os.listdir(metadata_dir):
        if metadata_file.endswith('.json'):
            with open(os.path.join(metadata_dir, metadata_file), 'r') as f:
                image_metadata = json.load(f)
            gallery_data['images'].append(image_metadata)

    # Sort images by date taken if available
    gallery_data['images'].sort(key=lambda x: x['exif'].get('DateTimeOriginal', ''))

    return gallery_data

def main():
    galleries_data = {
        "last_updated": datetime.now().isoformat(),
        "galleries": []
    }

    for gallery in os.listdir(config['source_path']):
        gallery_name = os.path.splitext(os.path.basename(gallery))[0]
        source_path = os.path.join(config['source_path'], gallery_name)
        output_path = os.path.join(config['output_path'], 'galleries', gallery_name)
        if os.path.isdir(source_path):
            print(f"*** Processing gallery {gallery_name}",end="",flush=True)
            gallery_data = process_gallery(source_path, output_path)
            print(".",end="",flush=True)
            galleries_data['galleries'].append(gallery_data)
            print(".",end="",flush=True)
            gallery_json_output_path = os.path.join(output_path, 'index.json')
            with open(gallery_json_output_path, 'w') as f:
                json.dump(gallery_data, f, indent=2)
            print(".",end="",flush=True)
            print("OK",flush=True)

    # Sort galleries by date, most recent first
    galleries_data['galleries'].sort(key=lambda x: x['date'], reverse=True)

    # Write galleries.json
    json_output_path = os.path.join(config['output_path'], 'galleries', 'galleries.json')
    with open(json_output_path, 'w') as f:
        json.dump(galleries_data, f, indent=2)

if __name__ == "__main__":
    main()