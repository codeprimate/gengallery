#!/usr/bin/env python

"""
Image Processing Script for Gallery Management

A comprehensive image processing utility that handles gallery image preparation,
including EXIF extraction, resizing, encryption, and metadata management.

Key Features:
    - Multi-format image processing (JPEG, PNG, TIFF, etc.)
    - EXIF metadata extraction and formatting
    - Automatic thumbnail and web-optimized image generation
    - Optional envelope-v1 AES-256-GCM encryption for encrypted galleries
    - Deterministic ID generation for images and galleries
    - EXIF-based image rotation handling
    - Rich progress tracking and console output

Usage:
    Process single gallery:
        $ python image_processor.py gallery_name

    Process all galleries:
        $ python image_processor.py --all

Configuration:
    Settings are read from config.yaml, including:
    - Image dimensions for different views
    - JPEG quality settings
    - Input/output paths
    - EXIF fields to extract

Returns:
    0: Success
    1: No arguments provided
    2: No galleries found
    3: Processing errors occurred
    130: Keyboard interrupt

Requirements:
    PIL (Pillow)>=9.0.0
    pillow-heif>=0.13.0
    exif>=1.3.0
    cryptography>=37.0.0
    rich>=12.0.0
    pyyaml>=6.0.0
"""

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
import warnings
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text
import sys
from pillow_heif import register_heif_opener
from crypto_v1 import derive_storage_token_bytes, derive_image_key_bytes, derive_metadata_key_bytes
from envelope_v1 import encrypt_payload, decrypt_payload

# Suppress specific warnings
warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning, message="ASCII tag contains -1 fewer bytes than specified")
warnings.filterwarnings("ignore", category=UserWarning, message="Truncated File Read")

# Register HEIF opener with Pillow
register_heif_opener()

SUPPORTED_FORMATS = (
    '.bmp',  # Windows Bitmap
    '.gif',  # Graphics Interchange Format
    '.heic', '.heif',  # High Efficiency Image Format
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

console = Console()
ENCRYPTED_VARIANT_EXTENSION = '.enc'
PLAINTEXT_VARIANT_EXTENSION = '.jpg'
TEMP_PLAINTEXT_SUFFIX = '.tmp.jpg'
METADATA_VARIANT_DIR = 'metadata'
METADATA_BLOB_EXTENSION = '.enc'
GCM_NONCE_MATERIAL_PREFIX_IMAGE_VARIANT = 'pge-v1/gcm-nonce|image-variant'
GCM_NONCE_MATERIAL_PREFIX_METADATA_BLOB = 'pge-v1/gcm-nonce|metadata-blob'
INNER_METADATA_SCHEMA_VERSION = 1
STALE_ENCRYPTED_EXTENSIONS = (
    '.jpg',
    '.jpeg',
    '.png',
    '.webp',
    '.gif',
    '.bmp',
    '.tif',
    '.tiff',
    '.mp4',
    '.mov',
    '.m4v',
    '.temp',
    '.bin',
    '.encrypted'
)

def generate_image_id(image_path: str, gallery_id: str) -> str:
    """
    Generate a unique ID for an image based on its path and gallery.
    
    The ID is created by hashing the combination of gallery ID and image path,
    ensuring uniqueness within the gallery context while remaining deterministic.
    
    Args:
        image_path: Path to the image file
        gallery_id: ID of the gallery containing the image
    
    Returns:
        A 12-character hexadecimal ID string
    """
    unique_string = f"{gallery_id}:{image_path}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:12]

def get_pil_exif_data(img: Image.Image) -> dict:
    """
    Extract EXIF data from a PIL Image object.
    
    Args:
        img (PIL.Image.Image): PIL Image object to extract EXIF from
    
    Returns:
        dict: Dictionary containing relevant EXIF data
    """
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

def get_exif_data(image_path: str) -> dict:
    """
    Extract comprehensive EXIF data from an image file.

    Args:
        image_path: Path to the image file

    Returns:
        dict: Formatted EXIF data including:
            - Camera make and model
            - Lens information
            - Shooting parameters (exposure, aperture, ISO)
            - Date and time
            - GPS coordinates (if available)

    Note:
        Handles special cases like exposure fractions and unit formatting.
    """
    with open(image_path, 'rb') as image_file:
        img = exif.Image(image_file)
    
    if not img.has_exif:
        return {}

    exif_data = {}
    
    # Extract relevant EXIF data
    exif_fields = [
        ('Orientation', 'orientation'),
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

def get_lat_lon(img: exif.Image) -> tuple[float | None, float | None]:
    """
    Extract GPS coordinates from image EXIF data.

    Args:
        img: EXIF image object

    Returns:
        tuple: (latitude, longitude) as floats, or (None, None) if not available.
        Coordinates are in decimal degrees, negative for South/West.
    """
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

def derive_encryption_params(gallery_id: str, image_id: str, password: str, source_file: str = None) -> bytes:
    """
    Derive deterministic encryption key for gallery image payloads.

    Args:
        gallery_id: Unique identifier for the gallery
        image_id: Unique identifier for the image
        password: User-provided encryption password
        source_file: Optional source file path for additional entropy

    Returns:
        bytes: 32-byte AES-GCM image key

    Note:
        The key derivation process ensures deterministic key generation
        across build/runtime implementations.
    """
    storage_token_bytes = derive_storage_token_bytes(password, gallery_id)
    key = derive_image_key_bytes(storage_token_bytes, gallery_id)
    
    return key

def encrypt_file(file_path: str, key: bytes, nonce_material: bytes) -> bytes:
    """
    Encrypt file contents using envelope-v1 AES-256-GCM.

    ``nonce_material`` must be unique for each encryption that uses the same key.
    """
    with open(file_path, 'rb') as f:
        data = f.read()
    return encrypt_payload(data, key, nonce_material=nonce_material)

def get_variant_extension(is_encrypted: bool) -> str:
    """Return expected variant file extension for the gallery mode."""
    return ENCRYPTED_VARIANT_EXTENSION if is_encrypted else PLAINTEXT_VARIANT_EXTENSION

def clean_encrypted_variant_outputs(gallery_id: str) -> None:
    """
    Remove stale plaintext and legacy encrypted variant artifacts for encrypted galleries.
    """
    gallery_variants_root = os.path.join(
        config['output_path'],
        'public_html',
        'galleries',
        gallery_id
    )
    variant_dirs = list(config['image_sizes'].keys()) + [METADATA_VARIANT_DIR, 'video']
    for variant_dir in variant_dirs:
        variant_path = os.path.join(gallery_variants_root, variant_dir)
        if not os.path.isdir(variant_path):
            continue
        for file_name in os.listdir(variant_path):
            full_path = os.path.join(variant_path, file_name)
            if not os.path.isfile(full_path):
                continue
            lower_name = file_name.lower()
            if lower_name.endswith(STALE_ENCRYPTED_EXTENSIONS):
                os.remove(full_path)

def check_output_files(image_path: str, gallery_id: str, image_id: str, is_encrypted: bool) -> bool:
    """
    Check if all output files exist and are newer than source files.

    Args:
        image_path: Path to the source image
        gallery_id: ID of the gallery
        image_id: ID of the image

    Returns:
        bool: True if all output files are up to date, False if any need processing

    Note:
        Checks modification times of source image, config files, and all size variants.
    """
    # Get the latest modification time among source files
    source_mtimes = [
        os.path.getmtime(image_path),  # Image modification time
        os.path.getmtime('config.yaml'),  # Global config modification time
        os.path.getmtime(os.path.join(config['source_path'], gallery_id, 'gallery.yaml'))  # Gallery config modification time
    ]
    latest_source_mtime = max(source_mtimes)
    
    # Check each size variant
    variant_extension = get_variant_extension(is_encrypted)
    for size_name in config['image_sizes'].keys():
        output_path = os.path.join(
            config['output_path'], 
            'public_html', 
            'galleries',
            gallery_id, 
            size_name,
            f"{image_id}{variant_extension}"
        )
        if not os.path.exists(output_path):
            return False
        if os.path.getmtime(output_path) < latest_source_mtime:
            return False
    
    # Check metadata file
    metadata_path = os.path.join(
        config['output_path'],
        'metadata',
        gallery_id,
        f"{image_id}.json"
    )
    if not os.path.exists(metadata_path):
        return False
    if os.path.getmtime(metadata_path) < latest_source_mtime:
        return False

    if is_encrypted:
        metadata_blob_path = os.path.join(
            config['output_path'],
            'public_html',
            'galleries',
            gallery_id,
            METADATA_VARIANT_DIR,
            f"{image_id}{METADATA_BLOB_EXTENSION}"
        )
        if not os.path.exists(metadata_blob_path):
            return False
        if os.path.getmtime(metadata_blob_path) < latest_source_mtime:
            return False
    
    return True

def verify_encryption(encrypted_path: str, original_path: str, password: str, gallery_id: str = None) -> bool:
    """
    Verify that an encrypted file can be decrypted back to the original.

    Args:
        encrypted_path: Path to the encrypted file
        original_path: Path to the original file
        password: Encryption password

    Returns:
        bool: True if verification succeeds

    Raises:
        ValueError: If decrypted content doesn't match original
    """
    # Read files and calculate initial hashes
    with open(original_path, 'rb') as f:
        original_data = f.read()
        original_hash = hashlib.md5(original_data).hexdigest()
    
    with open(encrypted_path, 'rb') as f:
        encrypted_data = f.read()
    
    if not gallery_id:
        raise ValueError('gallery_id is required for v1 verification')
    storage_token_bytes = derive_storage_token_bytes(password, gallery_id)
    key_bytes = derive_image_key_bytes(storage_token_bytes, gallery_id)
    decrypted_data = decrypt_payload(encrypted_data, key_bytes)
    decrypted_hash = hashlib.md5(decrypted_data).hexdigest()
    
    if original_hash != decrypted_hash:
        raise ValueError("Encryption verification failed - hashes do not match")
    
    return True

def extract_image_data(image_path: str, img_file, img: Image.Image) -> tuple[dict, float, float]:
    """
    Extract EXIF and location data from an image file.
    
    Args:
        image_path: Path to the image file
        img_file: Open file handle for raw EXIF extraction
        img: PIL Image object for fallback EXIF extraction
    
    Returns:
        tuple: (exif_data, latitude, longitude)
    """
    try:
        exif_img = exif.Image(img_file)
        exif_data = get_exif_data(image_path)
        lat, lon = get_lat_lon(exif_img)
    except (UnpackError, ValueError):
        exif_data = get_pil_exif_data(img)  # Now img is properly defined
        lat, lon = None, None
    
    # Handle missing date
    if 'DateTimeOriginal' not in exif_data:
        file_mtime = os.path.getmtime(image_path)
        exif_data['DateTimeOriginal'] = datetime.fromtimestamp(file_mtime).strftime('%Y:%m:%d %H:%M:%S')
    
    return exif_data, lat, lon

def create_metadata_dict(image_path: str, image_id: str, gallery_id: str,
                        exif_data: dict, lat: float, lon: float, is_encrypted: bool) -> dict:
    """
    Create the metadata dictionary for an image.
    """
    image_metadata = get_image_metadata(image_path)
    filename = os.path.basename(image_path)
    
    variant_extension = get_variant_extension(is_encrypted)
    metadata = {
        "id": image_id,
        "filename": filename,
        "url": f"/galleries/{gallery_id}/{image_id}.html",
        "path": f"/galleries/{gallery_id}/full/{image_id}{variant_extension}",
        "thumbnail_path": f"/galleries/{gallery_id}/thumbnail/{image_id}{variant_extension}",
        "cover_path": f"/galleries/{gallery_id}/cover/{image_id}{variant_extension}",
        "title": image_metadata.get('title', os.path.splitext(filename)[0].replace('_', ' ').title()),
        "caption": image_metadata.get('caption', ''),
        "tags": image_metadata.get('tags', []),
        "lat": lat,
        "lon": lon,
        "exif": exif_data
    }
    if is_encrypted:
        metadata["metadata_path"] = f"/galleries/{gallery_id}/{METADATA_VARIANT_DIR}/{image_id}{METADATA_BLOB_EXTENSION}"
    return metadata

def create_public_metadata_dict(output_metadata: dict, is_encrypted: bool) -> dict:
    """Build metadata payload written to plaintext export metadata JSON."""
    if not is_encrypted:
        return output_metadata

    return {
        "id": output_metadata["id"],
        "url": output_metadata["url"],
        "path": output_metadata["path"],
        "thumbnail_path": output_metadata["thumbnail_path"],
        "cover_path": output_metadata["cover_path"],
        "metadata_path": output_metadata.get("metadata_path", "")
    }

def create_inner_metadata_dict(output_metadata: dict) -> dict:
    """Create inner metadata JSON schema for encrypted metadata blob."""
    return {
        "inner_schema_version": INNER_METADATA_SCHEMA_VERSION,
        "image_id": output_metadata["id"],
        "filename": output_metadata["filename"],
        "title": output_metadata.get("title", ""),
        "caption": output_metadata.get("caption", ""),
        "exif": output_metadata.get("exif", {}),
        "tags": output_metadata.get("tags", [])
    }

def write_encrypted_metadata_blob(output_metadata: dict, gallery_id: str, password: str) -> None:
    """Emit encrypted metadata blob under public_html for encrypted galleries."""
    storage_token_bytes = derive_storage_token_bytes(password, gallery_id)
    metadata_key = derive_metadata_key_bytes(storage_token_bytes, gallery_id)
    inner_metadata_bytes = json.dumps(
        create_inner_metadata_dict(output_metadata),
        separators=(',', ':'),
        ensure_ascii=True
    ).encode('utf-8')
    nonce_material = (
        f'{GCM_NONCE_MATERIAL_PREFIX_METADATA_BLOB}|{gallery_id}|{output_metadata["id"]}'
    ).encode('utf-8')
    encrypted_blob = encrypt_payload(
        inner_metadata_bytes, metadata_key, nonce_material=nonce_material
    )
    metadata_output_dir = os.path.join(
        config['output_path'],
        'public_html',
        'galleries',
        gallery_id,
        METADATA_VARIANT_DIR
    )
    os.makedirs(metadata_output_dir, exist_ok=True)
    metadata_blob_path = os.path.join(
        metadata_output_dir,
        f"{output_metadata['id']}{METADATA_BLOB_EXTENSION}"
    )
    with open(metadata_blob_path, 'wb') as metadata_blob_file:
        metadata_blob_file.write(encrypted_blob)

def process_image_variants(img: Image.Image, image_id: str, gallery_id: str, 
                         is_encrypted: bool, gallery_config: dict) -> None:
    """
    Process and save all size variants of an image.
    """
    for size_name, max_size in config['image_sizes'].items():
        output_dir = os.path.join(config['output_path'], 'public_html', 'galleries', 
                                gallery_id, size_name)
        os.makedirs(output_dir, exist_ok=True)
        variant_extension = get_variant_extension(is_encrypted)
        output_path = os.path.join(output_dir, f"{image_id}{variant_extension}")
        
        img_copy = img.copy()
        img_copy.thumbnail((max_size, max_size))
        
        if is_encrypted:
            temp_path = os.path.join(output_dir, f"{image_id}{TEMP_PLAINTEXT_SUFFIX}")
            try:
                # Save unencrypted version to temp file
                img_copy.save(temp_path, "JPEG", quality=config['jpg_quality'])
                
                # Encrypt the file
                key = derive_encryption_params(gallery_id, image_id, gallery_config['password'])
                nonce_material = (
                    f'{GCM_NONCE_MATERIAL_PREFIX_IMAGE_VARIANT}|{gallery_id}|{image_id}|{size_name}'
                ).encode('utf-8')
                encrypted_data = encrypt_file(temp_path, key, nonce_material)
                
                # Write encrypted data
                with open(output_path, 'wb') as f:
                    f.write(encrypted_data)
            except Exception as e:
                raise ValueError(f"Encryption failed: {str(e)}")
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        else:
            img_copy.save(output_path, "JPEG", quality=config['jpg_quality'])

def process_image(image_path: str, gallery_id: str, gallery_config: dict, progress: Progress = None, 
                 image_number: int = None, total_images: int = None) -> dict:
    """
    Process a single image through the gallery preparation pipeline.
    """
    filename = os.path.basename(image_path)
    
    # Generate image ID and check if processing needed
    is_encrypted = gallery_config.get('encrypted', False)
    image_id = (hashlib.sha256(f"{gallery_id}:{filename}".encode()).hexdigest()[:16] 
                if is_encrypted else generate_image_id(filename, gallery_id))

    if check_output_files(image_path, gallery_id, image_id, is_encrypted):
        if progress:
            task = progress.add_task(
                f"[green]✓ Skipping {filename}[/] ({image_number}/{total_images})",
                total=100
            )
            progress.update(task, completed=100)
            progress.remove_task(task)
        
        # Return existing metadata
        metadata_path = os.path.join(config['output_path'], 'metadata', gallery_id, f"{image_id}.json")
        with open(metadata_path, 'r') as f:
            existing_metadata = json.load(f)
        if is_encrypted:
            public_metadata = create_public_metadata_dict(existing_metadata, True)
            if existing_metadata != public_metadata:
                with open(metadata_path, 'w') as metadata_file:
                    json.dump(public_metadata, metadata_file, indent=2)
            return public_metadata
        return existing_metadata

    if progress:
        task = progress.add_task(
            f"[cyan]{filename}[/] ({image_number}/{total_images})",
            total=100
        )
        progress.update(task, completed=5)

    with Image.open(image_path) as img, open(image_path, 'rb') as img_file:
        # Extract EXIF and location data
        exif_data, lat, lon = extract_image_data(image_path, img_file, img)
        if progress:
            progress.update(task, completed=25)

        # Create metadata dictionary
        output_metadata = create_metadata_dict(image_path, image_id, gallery_id, exif_data, lat, lon, is_encrypted)
        if progress:
            progress.update(task, completed=40)

        # Process image variants
        process_image_variants(img, image_id, gallery_id, is_encrypted, gallery_config)
        if is_encrypted:
            write_encrypted_metadata_blob(output_metadata, gallery_id, gallery_config['password'])
        if progress:
            progress.update(task, completed=90)

        # Save metadata
        metadata_dir = os.path.join(config['output_path'], 'metadata', gallery_id)
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_path = os.path.join(metadata_dir, f"{image_id}.json")
        with open(metadata_path, 'w') as f:
            json.dump(create_public_metadata_dict(output_metadata, is_encrypted), f, indent=2)

        if progress:
            progress.update(task, completed=100)
            progress.remove_task(task)

    return output_metadata

def get_image_metadata(image_path: str) -> dict:
    """
    Load metadata from an accompanying YAML file for an image.

    Args:
        image_path: Path to the image file

    Returns:
        dict: Image metadata including:
            - title: Image title (defaults to filename)
            - caption: Optional image description
            - tags: List of tags (empty list if none)
    """
    metadata_path = os.path.splitext(image_path)[0] + '.yaml'
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = yaml.safe_load(f) or {}
            # Ensure tags is always a list
            if 'tags' in metadata and not isinstance(metadata['tags'], list):
                metadata['tags'] = [metadata['tags']]
            elif 'tags' not in metadata:
                metadata['tags'] = []
            return metadata
    return {'tags': []}

def rotate_image(img: Image.Image, orientation: int) -> Image.Image:
    """
    Rotate and/or flip an image according to its EXIF orientation tag.

    Args:
        img: PIL Image object to transform
        orientation: EXIF orientation value (1-8):
            1: Normal (no rotation/flip needed)
            2: Mirrored horizontal
            3: Rotated 180°
            4: Mirrored vertical
            5: Mirrored horizontal then rotated 90° CCW
            6: Rotated 90° CW
            7: Mirrored horizontal then rotated 90° CW
            8: Rotated 90° CCW

    Returns:
        Image.Image: Transformed PIL Image object

    Note:
        Most digital cameras store images in landscape orientation (6).
        The transformation order matters for combined operations.
    """
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

def process_gallery(gallery: str) -> tuple[int, int]:
    """
    Process all supported images within a gallery directory.

    Args:
        gallery: Name of the gallery directory to process

    Returns:
        tuple: (successful_count, failed_count) indicating processing results

    Note:
        Gallery directory must contain gallery.yaml configuration file.
        Only processes files with supported extensions (see SUPPORTED_FORMATS).
    """
    success = failed = 0
    gallery_path = os.path.join(config['source_path'], gallery)
    
    if not os.path.isdir(gallery_path):
        return success, failed

    gallery_config_path = os.path.join(gallery_path, 'gallery.yaml')
    with open(gallery_config_path, 'r') as f:
        gallery_config = yaml.safe_load(f)
    if gallery_config.get('encrypted', False):
        clean_encrypted_variant_outputs(gallery)
    
    images = sorted(
        img for img in os.listdir(gallery_path)
        if img.lower().endswith(SUPPORTED_FORMATS)
    )
    
    if not images:
        return success, failed

    console.print(f"\n[bold yellow]⚡ Processing gallery: {gallery}[/]")
    console.print(f"  • Found [green]{len(images)}[/] images to process")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description: <50}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=True
    ) as progress:
        overall_task = progress.add_task(
            "[cyan]Overall Progress",
            total=len(images)
        )
        
        for idx, image in enumerate(images, 1):
            image_path = os.path.join(gallery_path, image)
            gallery_id = os.path.basename(gallery_path)
            
            try:
                process_image(image_path, gallery_id, gallery_config, progress, idx, len(images))
                success += 1
            except Exception as e:
                console.print(f"[red]Error processing {image}: {str(e)}[/]")
                failed += 1
            
            progress.advance(overall_task)

    return success, failed

def main() -> None:
    """
    Main entry point for the image processing script.

    Handles command line arguments and coordinates gallery processing.
    Provides real-time feedback and processing summary.

    Exit codes:
        0: Success - all images processed
        1: No arguments provided
        2: No galleries found
        3: One or more images failed
        130: Keyboard interrupt
    """
    try:
        parser = argparse.ArgumentParser(description='Process image galleries.')
        parser.add_argument('--all', action='store_true', help='Process all galleries')
        parser.add_argument('gallery', nargs='?', help='Name of the gallery to process')
        
        args = parser.parse_args()

        # Show welcome banner
        title = Text("Gallery Image Processor", style="bold cyan")
        console.print(Panel(title, border_style="cyan"))

        # Check for no arguments
        if not args.all and not args.gallery:
            parser.print_help()
            sys.exit(1)

        # Find galleries and count images
        console.print("\n[bold yellow]🔍 Finding galleries...[/]")
        galleries = []
        total_images = 0
        
        if args.all:
            gallery_paths = [g for g in os.listdir(config['source_path']) 
                          if os.path.isdir(os.path.join(config['source_path'], g))]
        else:
            gallery_paths = [args.gallery] if os.path.exists(os.path.join(config['source_path'], args.gallery)) else []

        # Count images in each gallery
        for gallery in gallery_paths:
            gallery_path = os.path.join(config['source_path'], gallery)
            images = sorted(
                img for img in os.listdir(gallery_path)
                if img.lower().endswith(SUPPORTED_FORMATS)
            )
            num_images = len(images)
            if num_images > 0:
                galleries.append((gallery, images))
                total_images += num_images
                console.print(f"  • [blue]{gallery}[/] → found [green]{num_images}[/] images")

        if not galleries:
            console.print("\n[red]❌ No galleries or images found[/]")
            sys.exit(2)

        console.print(f"[green]✓ Found {len(galleries)} galleries with {total_images} total images[/]")

        console.print("\n[bold yellow]⚡ Processing galleries...[/]")

        # Process galleries with nested progress bars
        total_success = total_failed = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description: <50}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
            expand=True
        ) as progress:
            overall_task = progress.add_task(
                "[cyan]Overall Progress",
                total=total_images
            )
            gallery_task = progress.add_task(
                "[blue]Gallery: None",
                total=None
            )

            for gallery_name, images in galleries:
                # Updated gallery progress description with highlighted name
                progress.update(gallery_task, 
                              description=f"[cyan]{gallery_name}[/] ({len(images)} images)",
                              total=len(images),
                              completed=0)

                gallery_config_path = os.path.join(config['source_path'], gallery_name, 'gallery.yaml')
                with open(gallery_config_path, 'r') as f:
                    gallery_config = yaml.safe_load(f)

                for idx, image in enumerate(images, 1):
                    image_path = os.path.join(config['source_path'], gallery_name, image)

                    try:
                        process_image(image_path, gallery_name, gallery_config, progress, idx, len(images))
                        total_success += 1
                    except Exception as e:
                        console.print(f"[red]Error processing {image}: {str(e)}[/]")
                        total_failed += 1

                    progress.advance(overall_task)
                    progress.advance(gallery_task)

                progress.update(gallery_task, completed=len(images))

        # Print summary
        console.print("\n[bold]Processing Summary[/]")
        console.print(f"  ✓ Successfully processed: [green]{total_success}[/] images")
        if total_failed:
            console.print(f"  ✗ Failed to process: [red]{total_failed}[/] images")
            sys.exit(3)
        
        console.print("\n[bold green]✨ All images processed successfully![/]")
        # sys.exit(0)

    except KeyboardInterrupt:
        console.print("\n[yellow]Processing interrupted by user[/]")
        sys.exit(130)

if __name__ == "__main__":
    main()