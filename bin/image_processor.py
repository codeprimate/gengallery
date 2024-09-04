#!/usr/bin/env python

import os
import json
import argparse
from datetime import datetime
from PIL import Image
from PIL import ExifTags
from plum.exceptions import UnpackError
import exif
import yaml
from fractions import Fraction
import hashlib

SUPPORTED_FORMATS = (
    '.bmp',  # Windows Bitmap
    '.gif',  # Graphics Interchange Format
    '.ico',  # Windows Icon
    '.jpg', '.jpeg', '.jpe',  # JPEG
    '.pcx',  # PCX
    '.png',  # Portable Network Graphics
    '.ppm', '.pgm', '.pbm', '.pnm',  # Portable Pixmap formats
    '.tga',  # TGA
    '.tiff', '.tif',  # Tagged Image File Format
    '.webp',  # WebP
    '.xbm',  # X Bitmap
)

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

def generate_image_id(image_path, gallery_id):
    unique_string = f"{gallery_id}:{image_path}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:12]

def get_pil_exif_data(img):
    exif_data = {}
    exif = img.getexif()
    if exif:
        for tag_id, value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if tag in ['Make', 'Model', 'LensModel', 'DateTimeOriginal', 'FocalLength', 'FNumber', 'ISOSpeedRatings', 'ExposureTime', 'ExposureBiasValue', 'MeteringMode', 'Flash', 'ExposureProgram']:
                if isinstance(value, bytes):
                    value = value.decode(errors='replace')
                exif_data[tag] = value
    return exif_data

def get_exif_data(image_path):
    with open(image_path, 'rb') as image_file:
        img = exif.Image(image_file)
    
    if not img.has_exif:
        return {}

    exif_data = {}
    
    # Extract relevant EXIF data
    exif_fields = [
        ('Make', 'make'),
        ('Model', 'model'),
        ('LensModel', 'lens_model'),
        ('DateTimeOriginal', 'datetime_original'),
        ('FocalLength', 'focal_length'),
        ('FNumber', 'f_number'),
        ('ISO', 'photographic_sensitivity'),
        ('ExposureTime', 'exposure_time'),
        ('ExposureCompensation', 'exposure_bias_value'),
        ('MeteringMode', 'metering_mode'),
        ('ExposureProgram', 'exposure_program'),
    ]

    for exif_tag, img_attr in exif_fields:
        if hasattr(img, img_attr):
            value = getattr(img, img_attr)
            if isinstance(value, Fraction):
                value = float(value)
            elif isinstance(value, exif.Flash):
                value = str(value)
            elif isinstance(value, (exif.MeteringMode, exif.ExposureProgram)):
                value = value.name
            exif_data[exif_tag] = value

    # Handle special cases
    if 'ExposureTime' in exif_data:
        exposure_time = Fraction(exif_data['ExposureTime']).limit_denominator()
        exif_data['ExposureTime'] = f"{exposure_time.numerator}/{exposure_time.denominator}"

    if 'FocalLength' in exif_data:
        exif_data['FocalLength'] = f"{exif_data['FocalLength']:.1f} mm"

    if 'FNumber' in exif_data:
        exif_data['FNumber'] = f"f/{exif_data['FNumber']:.1f}"

    if 'ExposureCompensation' in exif_data:
        exif_data['ExposureCompensation'] = f"{exif_data['ExposureCompensation']:.1f} EV"

    return exif_data

def get_lat_lon(img):
    if not img.has_exif:
        return None, None

    try:
        lat = img.gps_latitude
        lon = img.gps_longitude
        lat_ref = img.gps_latitude_ref
        lon_ref = img.gps_longitude_ref

        if lat and lon and lat_ref and lon_ref:
            lat = lat[0] + lat[1] / 60 + lat[2] / 3600
            lon = lon[0] + lon[1] / 60 + lon[2] / 3600
            if lat_ref != 'N':
                lat = -lat
            if lon_ref != 'E':
                lon = -lon
            return lat, lon
    except AttributeError:
        pass

    return None, None

def process_image(image_path, gallery_id):
    with Image.open(image_path) as img, open(image_path, 'rb') as img_file:
        filename = os.path.basename(image_path)
        image_id = generate_image_id(filename, gallery_id)

        try:
            exif_img = exif.Image(img_file)
            exif_data = get_exif_data(image_path)
            lat, lon = get_lat_lon(exif_img)
        except (UnpackError, ValueError) as e:
            exif_data = get_pil_exif_data(img)
            lat, lon = None, None

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

        # Update the metadata path
        metadata_dir = os.path.join(config['output_path'], 'metadata', gallery_id)
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_path = os.path.join(metadata_dir, f"{image_id}.json")
        with open(metadata_path, 'w') as f:
            json.dump(output_metadata, f, indent=2)

        # Resize and save images
        for size_name, max_size in config['image_sizes'].items():
            output_dir = os.path.join(config['output_path'], 'public_html', 'galleries', gallery_id, size_name)
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{image_id}.jpg")
            if not os.path.exists(output_path):
                img_copy = img.copy()
                img_copy.thumbnail((max_size, max_size))
                img_copy.save(output_path, "JPEG", quality=config['jpg_quality'])

    return output_metadata

def get_image_metadata(image_path):
    metadata_path = os.path.splitext(image_path)[0] + '.yaml'
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

def rotate_image(img, orientation):
    if orientation == 2:
        return img.transpose(Image.FLIP_LEFT_RIGHT)
    elif orientation == 3:
        return img.rotate(180)
    elif orientation == 4:
        return img.rotate(180).transpose(Image.FLIP_LEFT_RIGHT)
    elif orientation == 5:
        return img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
    elif orientation == 6:
        return img.rotate(-90, expand=True)
    elif orientation == 7:
        return img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
    elif orientation == 8:
        return img.rotate(90, expand=True)
    return img

def process_gallery(gallery):
    gallery_path = os.path.join(config['source_path'], gallery)
    if os.path.isdir(gallery_path):
        print(f"*** Processing images in gallery {gallery} ", end="", flush=True)
        images_dir = os.path.join(gallery_path)
        
        for image in os.listdir(images_dir):
            if image.lower().endswith(SUPPORTED_FORMATS):
                image_path = os.path.join(images_dir, image)
                gallery_id = os.path.basename(gallery_path)
                process_image(image_path, gallery_id)
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