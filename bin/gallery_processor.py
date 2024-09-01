#!/usr/bin/env python

import os
import json
import yaml
from datetime import datetime
import hashlib

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

def generate_image_id(image_path, gallery_id):
    unique_string = f"{gallery_id}:{image_path}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:12]

def process_gallery(gallery_path):
    # Load gallery.yaml
    with open(os.path.join(gallery_path, 'gallery.yaml'), 'r') as f:
        post_data = yaml.safe_load(f)

    gallery_id = os.path.basename(gallery_path)

    # Initialize gallery data
    gallery_data = {
        "id": gallery_id,
        "name": gallery_id,
        "last_updated": datetime.now().isoformat(),
        "title": post_data.get('title', ''),
        "date": post_data.get('date', '').isoformat(),
        "display_date": post_data.get('date', '').strftime('%A, %B %d, %Y'),
        "location": post_data.get('location', ''),
        "description": post_data.get('description', ''),
        "tags": post_data.get('tags', []),
        "content": post_data.get('content', ''),
        "images": []
    }

    # Process Security data
    password = post_data.get('password','')
    if password != '':
        private_gallery_id = hashlib.sha256(f"{gallery_id}:{password}".encode('utf-8')).hexdigest()[:16]
        gallery_data['private_gallery_id'] = private_gallery_id
        private_gallery_id_hash = hashlib.sha256(private_gallery_id.encode('utf-8')).hexdigest()
        gallery_data['private_gallery_id_hash'] = private_gallery_id_hash
    else:
        gallery_data['private_gallery_id'] = ''
        gallery_data['private_gallery_id_hash'] = ''
    if post_data.get('unlisted', False):
        gallery_data['unlisted'] = True
    else:
        gallery_data['unlisted'] = False

    # Process cover image
    cover_image_filename = post_data.get('cover', '')

    if cover_image_filename:
        image_path = os.path.join(gallery_id, cover_image_filename)
        cover_image_id = generate_image_id(cover_image_filename, gallery_id)
        cover_metadata_path = os.path.join(config['output_path'], 'metadata', gallery_id, f"{cover_image_id}.json")

        if os.path.exists(cover_metadata_path):
            with open(cover_metadata_path, 'r') as f:
                cover_metadata = json.load(f)
            gallery_data['cover'] = {
                "id": cover_metadata['id'],
                "filename": cover_metadata['filename'],
                "title": cover_metadata['title'],
                "caption": cover_metadata['caption'],
                "path": cover_metadata['cover_path'],
                "thumbnail_path": cover_metadata['thumbnail_path'],
            }
        else:
            gallery_data['cover'] = {
                "image_path": image_path,
                "cover_image_id": cover_image_id,
                "cover_metadata_path": cover_metadata_path,
                "id": cover_image_id,
                "filename": cover_image_filename,
                "title": '',
                "caption": '',
                "path": '',
                "thumbnail_path": ''
            }

    # Process all images
    metadata_dir = os.path.join(config['output_path'], 'metadata', gallery_id)
    for metadata_file in os.listdir(metadata_dir):
        if metadata_file.endswith('.json'):
            with open(os.path.join(metadata_dir, metadata_file), 'r') as f:
                image_metadata = json.load(f)
            gallery_data['images'].append(image_metadata)

    # Sort images by date taken if available
    gallery_data['images'].sort(key=lambda x: x['exif'].get('DateTimeOriginal', ''), reverse=True)

    return gallery_data

def main():
    galleries_data = {
        "last_updated": datetime.now().isoformat(),
        "galleries": []
    }

    for gallery in os.listdir(config['source_path']):
        gallery_name = os.path.splitext(os.path.basename(gallery))[0]
        source_path = os.path.join(config['source_path'], gallery_name)
        if os.path.isdir(source_path):
            print(f"*** Processing gallery {gallery_name}",end="",flush=True)
            gallery_data = process_gallery(source_path)
            print(".",end="",flush=True)
            galleries_data['galleries'].append(gallery_data)
            print(".",end="",flush=True)
            gallery_json_output_path = os.path.join(config['output_path'], 'metadata', gallery_name, 'index.json')
            os.makedirs(os.path.dirname(gallery_json_output_path), exist_ok=True)
            with open(gallery_json_output_path, 'w') as f:
                json.dump(gallery_data, f, indent=2)
            print(".",end="",flush=True)
            print("OK",flush=True)

    # Sort galleries by date
    galleries_data['galleries'].sort(key=lambda x: x['date'], reverse=True)

    # Write galleries.json
    json_output_path = os.path.join(config['output_path'], 'metadata', 'galleries.json')
    os.makedirs(os.path.dirname(json_output_path), exist_ok=True)
    with open(json_output_path, 'w') as f:
        json.dump(galleries_data, f, indent=2)

if __name__ == "__main__":
    main()