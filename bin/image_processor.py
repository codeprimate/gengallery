#!/usr/bin/env python

import os
import json
import argparse
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import yaml
from fractions import Fraction
import hashlib

SUPPORTED_FORMATS = ('.jpg', '.jpeg', '.png', '.webp', '.tiff')

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

def generate_image_id(image_path, gallery_id):
    # Generate a unique ID based on the image path and gallery ID
    unique_string = f"{gallery_id}:{image_path}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:12]

def get_exif_data(image):
    exif_data = {}
    info = image._getexif()
    if info:
        for tag_id, value in info.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in config['exif_fields']:
                if tag == 'GPSInfo':
                    gps_data = {}
                    for gps_tag_id in value:
                        gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                        gps_data[gps_tag] = value[gps_tag_id]
                    exif_data[tag] = gps_data
                else:
                    exif_data[tag] = convert_ifd_rational(value, tag)
    return exif_data

def get_lat_lon(gps_info):
    if not gps_info:
        return None, None

    lat = gps_info.get('GPSLatitude')
    lat_ref = gps_info.get('GPSLatitudeRef')
    lon = gps_info.get('GPSLongitude')
    lon_ref = gps_info.get('GPSLongitudeRef')

    if lat and lat_ref and lon and lon_ref:
        lat = sum(float(x)/float(y) for x, y in lat)
        if lat_ref != 'N':
            lat = -lat
        lon = sum(float(x)/float(y) for x, y in lon)
        if lon_ref != 'E':
            lon = -lon
        return lat, lon
    return None, None

def convert_ifd_rational(value, key=None):
    if isinstance(value, dict):
        return {k: convert_ifd_rational(v, k) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [convert_ifd_rational(item, key) for item in value]
    elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):
        if key == 'ExposureTime':
            return f"{value.numerator}/{value.denominator}"
        return float(Fraction(value.numerator, value.denominator))
    else:
        return value

def get_image_metadata(image_path):
    metadata_path = os.path.splitext(image_path)[0] + '.yaml'
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

def process_image(image_path, output_dir, gallery_id):
    print(f"\nprocess_image called for {image_path}")    
    with Image.open(image_path) as img:
        filename = os.path.basename(image_path)
        image_id = generate_image_id(filename, gallery_id)

        exif_data = get_exif_data(img)
        lat, lon = get_lat_lon(exif_data.get('GPSInfo'))
        if 'DateTimeOriginal' not in exif_data:
            file_mtime = os.path.getmtime(image_path)
            exif_data['DateTimeOriginal'] = datetime.fromtimestamp(file_mtime).strftime('%Y:%m:%d %H:%M:%S')

        image_metadata = get_image_metadata(image_path)
        
        output_metadata = {
            "id": image_id,
            "filename": filename,
            "url": f"/galleries/{gallery_id}/{image_id}.html",
            "path": f"/galleries/{gallery_id}/full/{image_id}.jpg",
            "thumbnail_path": f"/galleries/{gallery_id}/thumbnail/{image_id}.jpg",
            "cover_path": f"/galleries/{gallery_id}/cover/{image_id}.jpg",
            "title": image_metadata.get('title', os.path.splitext(os.path.basename(image_path))[0].replace('_', ' ').title()),
            "caption": image_metadata.get('caption', ''),
            "lat": lat,
            "lon": lon,
            "exif": exif_data
        }
        metadata_path = os.path.join(output_dir, 'metadata', f"{image_id}.json")
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        with open(metadata_path, 'w') as f:
            json.dump(output_metadata, f, indent=2)

        # Resize and save images
        for size_name, max_size in config['image_sizes'].items():
            output_path = os.path.join(output_dir, size_name, f"{image_id}.jpg")
            if not os.path.exists(output_path):
                img_copy = img.copy()
                img_copy.thumbnail((max_size, max_size))
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                img_copy.save(output_path, "JPEG", quality=config['jpg_quality'])

    return output_metadata

def process_gallery(gallery):
    gallery_path = os.path.join(config['source_path'], gallery)
    if os.path.isdir(gallery_path):
        print(f"*** Processing images in gallery {gallery} ", end="", flush=True)
        images_dir = os.path.join(gallery_path)
        output_dir = os.path.join(config['output_path'], 'galleries', gallery)
        
        for image in os.listdir(images_dir):
            if image.lower().endswith(SUPPORTED_FORMATS):
                image_path = os.path.join(images_dir, image)
                gallery_id = os.path.basename(gallery_path)
                process_image(image_path, output_dir, gallery_id)
                print(".", end="", flush=True)
        print("OK", flush=True)

def main():
    parser = argparse.ArgumentParser(description='Process image galleries.')
    parser.add_argument('--all', action='store_true', help='Process all galleries')
    parser.add_argument('gallery', nargs='?', help='Name of the gallery to process')
    
    args = parser.parse_args()

    if args.all:
        for gallery in os.listdir(config['source_path']):
            process_gallery(gallery)
    elif args.gallery:
        if os.path.exists(os.path.join(config['source_path'], args.gallery)):
            process_gallery(args.gallery)
        else:
            print(f"Error: Gallery '{args.gallery}' not found.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()