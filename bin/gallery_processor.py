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
        gallery_config = yaml.safe_load(f)

    gallery_id = os.path.basename(gallery_path)

    # Initialize gallery data
    gallery_data = {
        "id": gallery_id,
        "name": gallery_id,
        "last_updated": datetime.now().strftime('%Y:%m:%d %H:%M:%S'),
        "title": gallery_config.get('title', ''),
        "date": gallery_config.get('date', '').strftime('%Y:%m:%d %H:%M:%S'),
        "display_date": gallery_config.get('date', '').strftime('%A, %B %d, %Y'),
        "location": gallery_config.get('location', ''),
        "description": gallery_config.get('description', ''),
        "tags": gallery_config.get('tags', []),
        "content": gallery_config.get('content', ''),
        "images": []
    }

    # Process Security data
    password = gallery_config.get('password','')
    if password != '':
        private_gallery_id = hashlib.sha256(f"{gallery_id}:{password}".encode('utf-8')).hexdigest()[:16]
        private_gallery_id_hash = hashlib.sha256(private_gallery_id.encode('utf-8')).hexdigest()
        gallery_data['private_gallery_id'] = private_gallery_id
        gallery_data['private_gallery_id_hash'] = private_gallery_id_hash
    else:
        gallery_data['private_gallery_id'] = ''
        gallery_data['private_gallery_id_hash'] = ''
    if gallery_config.get('unlisted', False):
        gallery_data['unlisted'] = True
    else:
        gallery_data['unlisted'] = False

    # Process image metadata
    metadata_dir = os.path.join(config['output_path'], 'metadata', gallery_id)
    for metadata_file in os.listdir(metadata_dir):
        if metadata_file != 'index.json' and metadata_file.endswith('.json'):
            metadata_path = os.path.join(metadata_dir, metadata_file)
            with open(metadata_path, 'r') as f:
                image_metadata = json.load(f)
            
            # Check if the original image still exists
            original_image_path = os.path.join(gallery_path, image_metadata['filename'])
            if os.path.exists(original_image_path):
                gallery_data['images'].append(image_metadata)
            else:
                # Remove metadata file
                os.remove(metadata_path)
                
                # Remove image files from output directories
                for size_name in config['image_sizes'].keys():
                    output_image_path = os.path.join(config['output_path'], 'public_html', 'galleries', gallery_id, size_name, f"{image_metadata['id']}.jpg")
                    if os.path.exists(output_image_path):
                        os.remove(output_image_path)
                
                print(f"Removed files for non-existent image: {image_metadata['filename']}")


    # Process cover image
    cover_image_filename = gallery_config.get('cover', '')
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
            gallery_data['cover'] = gallery_data['images'][0]

    # Sort images by date taken if available
    gallery_data['images'].sort(key=lambda x: x['exif'].get('DateTimeOriginal', ''), reverse=True)

    # Determine the latest updated timestamp of any files in the source gallery directory
    latest_timestamp = max(os.path.getmtime(os.path.join(gallery_path, f)) for f in os.listdir(gallery_path) if os.path.isfile(os.path.join(gallery_path, f)))
    gallery_data['last_updated'] = datetime.fromtimestamp(latest_timestamp).strftime('%Y:%m:%d %H:%M:%S')

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