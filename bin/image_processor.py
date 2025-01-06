#!/usr/bin/env python

"""
Image Processing Script for Gallery Management

A comprehensive image processing utility that handles gallery image preparation,
including EXIF extraction, resizing, encryption, and metadata management.

Key Features:
    - Multi-format image processing (JPEG, PNG, TIFF, etc.)
    - EXIF metadata extraction and formatting
    - Automatic thumbnail and web-optimized image generation
    - Optional AES-CBC encryption for private galleries
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
import secrets  # Add this import for secure random bytes generation
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text
import sys
from pillow_heif import register_heif_opener

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

def derive_encryption_params(gallery_id: str, image_id: str, password: str, source_file: str = None) -> tuple[bytes, bytes]:
    """
    Derive deterministic encryption key and initialization vector.

    Args:
        gallery_id: Unique identifier for the gallery
        image_id: Unique identifier for the image
        password: User-provided encryption password
        source_file: Optional source file path for additional entropy

    Returns:
        tuple: (key, iv) where:
            - key (bytes): 32-byte AES encryption key
            - iv (bytes): 16-byte initialization vector

    Note:
        The key derivation process ensures the same key/IV pair will be
        generated for the same input parameters, allowing for deterministic
        encryption/decryption across different sessions.
    """
    # First generate the private gallery ID (this matches the client-side logic)
    combined = f"{gallery_id}:{password}"
    private_gallery_id = hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    # Use the private gallery ID to generate the encryption key
    key = hashlib.sha256(private_gallery_id.encode()).digest()
    
    # Generate IV from image ID
    iv = hashlib.sha256(image_id.encode()).digest()[:16]
    
    return key, iv

def encrypt_file(file_path: str, key: bytes, iv: bytes) -> bytes:
    """
    Encrypt a file using AES-CBC with the provided key and IV.
    """
    # Create cipher
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    
    # Read and pad the file data
    with open(file_path, 'rb') as f:
        data = f.read()
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    
    # Encrypt the data
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    # Return encrypted data only - IV is derived deterministically on client
    return encrypted_data

def check_output_files(image_path: str, gallery_id: str, image_id: str) -> bool:
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
    for size_name in config['image_sizes'].keys():
        output_path = os.path.join(
            config['output_path'], 
            'public_html', 
            'galleries',
            gallery_id, 
            size_name,
            f"{image_id}.jpg"
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
    
    return True

def verify_encryption(encrypted_path: str, original_path: str, password: str) -> bool:
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
    
    # Extract IV and encrypted data
    iv = encrypted_data[:16]
    data = encrypted_data[16:]
    
    # Create key and decrypt
    key_bytes = hashlib.sha256(password.encode()).digest()
    
    # Perform decryption and verification
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv))
    decryptor = cipher.decryptor()
    decrypted_padded = decryptor.update(data) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()
    decrypted_hash = hashlib.md5(decrypted_data).hexdigest()
    
    if original_hash != decrypted_hash:
        raise ValueError("Encryption verification failed - hashes do not match")
    
    return True

def process_image(image_path: str, gallery_id: str, gallery_config: dict, progress: Progress = None, 
                 image_number: int = None, total_images: int = None) -> dict:
    """
    Process a single image through the gallery preparation pipeline.

    The processing pipeline includes:
    1. Image validation and ID generation
    2. EXIF metadata extraction
    3. Multiple size variant creation
    4. Optional encryption
    5. Metadata storage

    Args:
        image_path: Path to source image file
        gallery_id: Unique gallery identifier
        gallery_config: Gallery configuration dict with:
            - encrypted (bool): Enable encryption
            - password (str, optional): Encryption password
        progress: Optional rich.Progress instance
        image_number: Current image number for progress
        total_images: Total images being processed

    Returns:
        dict: Processed image metadata including:
            - id: Unique image identifier
            - filename: Original filename
            - url: Web access URL
            - paths: Variant image paths
            - title/caption/tags: Image metadata
            - lat/lon: GPS coordinates if available
            - exif: Formatted EXIF data
            If encrypted:
            - encrypted: True
            - salt/iv: Encryption parameters

    Raises:
        PIL.UnidentifiedImageError: Unsupported image format
        OSError: File system access errors
        ValueError: Invalid gallery configuration
    """
    filename = os.path.basename(image_path)
    
    # Generate image ID early to check if processing is needed
    if gallery_config.get('encrypted', False):
        image_id = hashlib.sha256(f"{gallery_id}:{filename}".encode()).hexdigest()[:16]
    else:
        image_id = generate_image_id(filename, gallery_id)

    # Check if processing is needed
    if check_output_files(image_path, gallery_id, image_id):
        if progress:
            task = progress.add_task(
                f"[green]✓ Skipping {filename}[/] ({image_number}/{total_images})",
                total=100
            )
            progress.update(task, completed=100)
            progress.remove_task(task)
        
        # Load and return existing metadata
        metadata_path = os.path.join(
            config['output_path'],
            'metadata',
            gallery_id,
            f"{image_id}.json"
        )
        with open(metadata_path, 'r') as f:
            return json.load(f)

    is_encrypted = gallery_config.get('encrypted', False)
    
    # Updated progress description with highlighted filename
    if progress:
        task = progress.add_task(
            f"[cyan]{filename}[/] ({image_number}/{total_images})",
            total=100,
            columns=[
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn()
            ]
        )

    # Opening image (5%)
    with Image.open(image_path) as img, open(image_path, 'rb') as img_file:
        if progress:
            progress.update(task, completed=5)

        # Extract EXIF data (25%)
        try:
            exif_img = exif.Image(img_file)
            exif_data = get_exif_data(image_path)
            lat, lon = get_lat_lon(exif_img)
        except (UnpackError, ValueError) as e:
            exif_data = get_pil_exif_data(img)
            lat, lon = None, None
        if progress:
            progress.update(task, completed=25)

        # Handle metadata (35%)
        if 'DateTimeOriginal' not in exif_data:
            file_mtime = os.path.getmtime(image_path)
            exif_data['DateTimeOriginal'] = datetime.fromtimestamp(file_mtime).strftime('%Y:%m:%d %H:%M:%S')
        image_metadata = get_image_metadata(image_path)
        if progress:
            progress.update(task, completed=35)

        # Create metadata dictionary (40%)
        output_metadata = {
            "id": image_id,
            "filename": filename,
            "url": f"/galleries/{gallery_id}/{image_id}.html",
            "path": f"/galleries/{gallery_id}/full/{image_id}.jpg",
            "thumbnail_path": f"/galleries/{gallery_id}/thumbnail/{image_id}.jpg",
            "cover_path": f"/galleries/{gallery_id}/cover/{image_id}.jpg",
            "title": image_metadata.get('title', os.path.splitext(os.path.basename(image_path))[0].replace('_', ' ').title()),
            "caption": image_metadata.get('caption', ''),
            "tags": image_metadata.get('tags', []),
            "lat": lat,
            "lon": lon,
            "exif": exif_data
        }
        if progress:
            progress.update(task, completed=40)

        # Process image sizes (40-90%)
        size_count = len(config['image_sizes'])
        for idx, (size_name, max_size) in enumerate(config['image_sizes'].items(), 1):
            output_dir = os.path.join(config['output_path'], 'public_html', 'galleries', 
                                    gallery_id, size_name)
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{image_id}.jpg")
            
            img_copy = img.copy()
            img_copy.thumbnail((max_size, max_size))
            
            if is_encrypted:
                try:
                    for size_name, max_size in config['image_sizes'].items():
                        output_dir = os.path.join(config['output_path'], 'public_html', 'galleries', 
                                                gallery_id, size_name)
                        os.makedirs(output_dir, exist_ok=True)
                        output_path = os.path.join(output_dir, f"{image_id}.jpg")
                        
                        # Save unencrypted version to temp file
                        temp_path = output_path + '.temp'
                        img_copy = img.copy()
                        img_copy.thumbnail((max_size, max_size))
                        img_copy.save(temp_path, "JPEG", quality=config['jpg_quality'])
                        
                        # Encrypt the file using private gallery ID
                        key, iv = derive_encryption_params(
                            gallery_id, 
                            image_id, 
                            gallery_config['password']
                        )
                        encrypted_data = encrypt_file(temp_path, key, iv)
                        
                        # Write encrypted data directly - don't prepend IV
                        with open(output_path, 'wb') as f:
                            f.write(encrypted_data)
                        
                        # Clean up temp file
                        os.unlink(temp_path)
                        
                except Exception as e:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    raise ValueError(f"Encryption failed for {filename}: {str(e)}")
            else:
                img_copy.save(output_path, "JPEG", quality=config['jpg_quality'])
            
            if progress:
                # Calculate progress for each size (50% of total progress spread across sizes)
                size_progress = 40 + (50 * idx / size_count)
                progress.update(task, completed=size_progress)

        # Save metadata (100%)
        metadata_dir = os.path.join(config['output_path'], 'metadata', gallery_id)
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_path = os.path.join(metadata_dir, f"{image_id}.json")
        with open(metadata_path, 'w') as f:
            json.dump(output_metadata, f, indent=2)

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
    
    images = [img for img in os.listdir(gallery_path) 
             if img.lower().endswith(SUPPORTED_FORMATS)]
    
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
            images = [img for img in os.listdir(gallery_path) 
                     if img.lower().endswith(SUPPORTED_FORMATS)]
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