#!/usr/bin/env python

"""
Gallery Processor Script

A command-line tool for processing image galleries and generating metadata.

This script handles:
- Reading and processing gallery configurations from YAML files
- Processing image metadata and organizing gallery structures
- Supporting both regular and encrypted galleries
- Generating unique IDs and handling password-protected galleries
- Creating consolidated gallery metadata files

The script expects a config.yaml file in the current directory with the following structure:
    source_path: Path to source galleries
    output_path: Path for processed output
    image_sizes: Dictionary of image size configurations
"""

import os
import json
import yaml
import sys
from datetime import datetime
import hashlib
import base64
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from crypto_v1 import (
    derive_storage_token_bytes,
    derive_storage_token_hash_hex,
    get_gallery_salt_bytes,
    STORAGE_TOKEN_INFO_PREFIX,
)

console = Console()

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

MANIFEST_FILENAME = 'manifest.json'
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_CRYPTO_SUITE = 'pge-v1'
MANIFEST_KDF = 'hkdf-sha256-v1'
MANIFEST_SALT_SOURCE = 'gallery_id_utf8'
MANIFEST_VARIANT_FORMAT_VERSION = 1

def generate_image_id(image_path: str, gallery_id: str) -> str:
    """
    Generate a unique ID for an image based on its path and gallery ID.

    Args:
        image_path: Path to the image file
        gallery_id: ID of the gallery containing the image

    Returns:
        A 12-character hexadecimal hash uniquely identifying the image

    Example:
        >>> generate_image_id("photos/sunset.jpg", "summer2023")
        '7a8b9c0d1e2f'
    """
    unique_string = f"{gallery_id}:{image_path}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:12]

def cleanup_missing_image(gallery_id: str, image_metadata: dict, source_path: str) -> bool:
    """
    Clean up metadata and processed images for a missing source image.
    
    Args:
        gallery_id: ID of the gallery
        image_metadata: Metadata dictionary for the image
        source_path: Path to the source gallery directory
        
    Returns:
        bool: True if image was missing and cleaned up, False otherwise
    """
    filename = image_metadata.get('filename', '')
    if not filename:
        # Encrypted gallery metadata intentionally omits source filename.
        return False

    if os.path.exists(os.path.join(source_path, filename)):
        return False
        
    # Remove metadata file
    metadata_path = os.path.join(config['output_path'], 'metadata', gallery_id, f"{image_metadata['id']}.json")
    if os.path.exists(metadata_path):
        os.remove(metadata_path)
        console.print(f"  [yellow]→[/] Removed image metadata: [blue]{metadata_path}[/]")
    
    # Remove processed images (legacy fallback paths)
    for size_name in config['image_sizes'].keys():
        legacy_output_image_path = os.path.join(
            config['output_path'], 'public_html', 'galleries',
            gallery_id, size_name, f"{image_metadata['id']}.jpg"
        )
        encrypted_output_image_path = os.path.join(
            config['output_path'], 'public_html', 'galleries',
            gallery_id, size_name, f"{image_metadata['id']}.enc"
        )
        for output_image_path in (legacy_output_image_path, encrypted_output_image_path):
            if os.path.exists(output_image_path):
                os.remove(output_image_path)
                console.print(f"  [yellow]→[/] Removed image: [blue]{output_image_path}[/]")

    # Remove metadata blob if present
    metadata_blob_relpath = image_metadata.get('metadata_path', '')
    if metadata_blob_relpath:
        metadata_blob_path = os.path.join(
            config['output_path'],
            'public_html',
            metadata_blob_relpath.lstrip('/')
        )
        if os.path.exists(metadata_blob_path):
            os.remove(metadata_blob_path)
            console.print(f"  [yellow]→[/] Removed metadata blob: [blue]{metadata_blob_path}[/]")
            
    return True

def get_variant_url(image_metadata: dict, gallery_id: str, variant_name: str) -> str:
    """Resolve variant URL from image metadata, with deterministic fallback."""
    variant_path_key = f'{variant_name}_path'
    if variant_name == 'full':
        return image_metadata.get('path', '')
    if variant_path_key in image_metadata:
        return image_metadata.get(variant_path_key, '')

    image_extension = os.path.splitext(image_metadata.get('path', ''))[1] or '.enc'
    return f"/galleries/{gallery_id}/{variant_name}/{image_metadata['id']}{image_extension}"

def create_manifest_dict(gallery_data: dict) -> dict:
    """Create public encrypted manifest schema v1 from gallery metadata."""
    variant_names = list(config.get('image_sizes', {}).keys())
    images = []
    for image in gallery_data.get('images', []):
        variants = {}
        for variant_name in variant_names:
            variant_url = get_variant_url(image, gallery_data['id'], variant_name)
            if variant_url:
                variants[variant_name] = {
                    'url': variant_url,
                    'format_version': MANIFEST_VARIANT_FORMAT_VERSION
                }

        image_entry = {
            'id': image['id'],
            'variants': variants,
            'metadata_url': image.get('metadata_path', '')
        }
        images.append(image_entry)

    return {
        'schema_version': MANIFEST_SCHEMA_VERSION,
        'gallery_id': gallery_data['id'],
        'encrypted': gallery_data.get('encrypted', False),
        'crypto': {
            'suite': MANIFEST_CRYPTO_SUITE,
            'kdf': MANIFEST_KDF,
            'salt_source': MANIFEST_SALT_SOURCE
        },
        'verifier': {
            'storage_token_hash_hex': gallery_data.get('storage_token_hash_hex', '')
        },
        'images': images
    }

def write_manifest_file(gallery_data: dict) -> str:
    """Write encrypted gallery manifest to public_html and return its URL path."""
    manifest_output_path = os.path.join(
        config['output_path'],
        'public_html',
        'galleries',
        gallery_data['id'],
        MANIFEST_FILENAME
    )
    os.makedirs(os.path.dirname(manifest_output_path), exist_ok=True)
    with open(manifest_output_path, 'w') as manifest_file:
        json.dump(create_manifest_dict(gallery_data), manifest_file, indent=2)
    return f"/galleries/{gallery_data['id']}/{MANIFEST_FILENAME}"

def process_gallery(gallery_path: str) -> dict:
    """
    Process a single gallery directory and generate its metadata.

    This function reads a gallery's configuration, processes its images, and generates
    a comprehensive metadata structure for the gallery.

    Args:
        gallery_path (str): Path to the gallery directory containing gallery.yaml and images

    Returns:
        dict: A gallery metadata structure with the following format:
            {
                "id": str,                    # Unique gallery identifier (directory name)
                "encrypted": bool,            # Whether gallery is password-protected
                "name": str,                  # Gallery name (same as id)
                "last_updated": str,          # Timestamp of last update (YYYY:MM:DD HH:MM:SS)
                "title": str,                 # Gallery title from config
                "date": str,                  # Gallery date (YYYY:MM:DD HH:MM:SS)
                "display_date": str,          # Formatted date (e.g., "Monday, January 1, 2024")
                "location": str,              # Gallery location from config
                "description": str,           # Gallery description from config
                "tags": List[str],            # List of gallery tags
                "content": str,               # Additional content/notes
                "images": List[dict],         # List of image metadata dictionaries
                "requires_login": bool,        # Whether login gate is enabled
                "storage_token_label": str,    # Token label/version marker
                "salt_b64": str,               # Placeholder until v1 KDF is implemented
                "storage_token_hash_hex": str, # Temporary verifier hash for gate checks
                "manifest_path": str,         # Public manifest path for encrypted galleries
                "unlisted": bool,             # Whether gallery is hidden from listings
                "cover": dict | None          # Cover image metadata or None
            }

    The cover image dictionary has the following structure:
        {
            "id": str,           # Unique image identifier
            "filename": str,     # Original image filename
            "title": str,        # Image title
            "caption": str,      # Image caption
            "path": str,         # Path to cover-sized image
            "thumbnail_path": str # Path to thumbnail image
        }

    Raises:
        ValueError: If gallery is marked as encrypted but no password is provided
        FileNotFoundError: If gallery.yaml or required directories are missing
        json.JSONDecodeError: If image metadata files are corrupted

    Note:
        - The function expects a gallery.yaml file in the gallery directory
        - Images are sorted by EXIF DateTimeOriginal in reverse chronological order
        - Missing source images are automatically cleaned up from the output
        - The last_updated timestamp is based on the newest file in the gallery
    """
    gallery_id = os.path.basename(gallery_path)
    
    # Load gallery.yaml
    with open(os.path.join(gallery_path, 'gallery.yaml'), 'r') as f:
        gallery_config = yaml.safe_load(f)

    is_encrypted = gallery_config.get('encrypted', False)
    password = gallery_config.get('password', False)
    
    # Validate password for encrypted galleries
    if is_encrypted and not password:
        raise ValueError(f"Gallery '{gallery_id}' is marked as encrypted but no password was provided")

    # Initialize gallery data
    gallery_data = {
        "id": gallery_id,
        "encrypted": is_encrypted,
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
    
    if password:
        storage_token_bytes = derive_storage_token_bytes(password, gallery_id)
        storage_token_hash_hex = derive_storage_token_hash_hex(storage_token_bytes)
        salt_b64 = base64.urlsafe_b64encode(get_gallery_salt_bytes(gallery_id)).decode('ascii').rstrip('=')
        gallery_data['requires_login'] = True
        gallery_data['storage_token_label'] = STORAGE_TOKEN_INFO_PREFIX.rstrip(':')
        gallery_data['salt_b64'] = salt_b64
        gallery_data['storage_token_hash_hex'] = storage_token_hash_hex
        gallery_data['manifest_path'] = ''
    else:
        gallery_data['requires_login'] = False
        gallery_data['storage_token_label'] = ''
        gallery_data['salt_b64'] = ''
        gallery_data['storage_token_hash_hex'] = ''
        gallery_data['manifest_path'] = ''

    # Handle unlisted galleries - encrypted galleries are always unlisted
    gallery_data['unlisted'] = is_encrypted or gallery_config.get('unlisted', False)

    metadata_dir = os.path.join(config['output_path'], 'metadata', gallery_id)
    image_files = [f for f in os.listdir(metadata_dir) 
                   if f != 'index.json' and f.endswith('.json')]
    
    cleanup_occurred = False
    for metadata_file in image_files:
        metadata_path = os.path.join(metadata_dir, metadata_file)
        with open(metadata_path, 'r') as f:
            image_metadata = json.load(f)
        
        # Track if any cleanup occurred
        if cleanup_missing_image(gallery_id, image_metadata, gallery_path):
            cleanup_occurred = True
        else:
            gallery_data['images'].append(image_metadata)

    # Update last_updated if files were removed
    if cleanup_occurred:
        gallery_data['last_updated'] = datetime.now().strftime('%Y:%m:%d %H:%M:%S')

    # Process cover image
    cover_image_filename = gallery_config.get('cover', '')
    gallery_data['cover'] = None  # Initialize as None
    
    if cover_image_filename:
        # Try to find cover image by filename first (comparing basenames)
        cover_basename = os.path.splitext(cover_image_filename)[0]
        cover_image = next(
            (img for img in gallery_data['images'] 
             if img.get('filename') and os.path.splitext(img['filename'])[0] == cover_basename),
            None
        )
        if cover_image:
            if is_encrypted:
                gallery_data['cover'] = {
                    "id": cover_image['id'],
                    "path": cover_image['cover_path'],
                    "thumbnail_path": cover_image['thumbnail_path'],
                }
            else:
                gallery_data['cover'] = {
                    "id": cover_image['id'],
                    "filename": cover_image.get('filename', ''),
                    "title": cover_image.get('title', ''),
                    "caption": cover_image.get('caption', ''),
                    "path": cover_image['cover_path'],
                    "thumbnail_path": cover_image['thumbnail_path'],
                }
    
    # Fallback to first image if we have images but no valid cover
    if not gallery_data['cover'] and gallery_data['images']:
        first_image = gallery_data['images'][0]
        if is_encrypted:
            gallery_data['cover'] = {
                "id": first_image['id'],
                "path": first_image['cover_path'],
                "thumbnail_path": first_image['thumbnail_path'],
            }
        else:
            gallery_data['cover'] = {
                "id": first_image['id'],
                "filename": first_image.get('filename', ''),
                "title": first_image.get('title', ''),
                "caption": first_image.get('caption', ''),
                "path": first_image['cover_path'],
                "thumbnail_path": first_image['thumbnail_path'],
            }

    # Sort images by date taken if available
    gallery_data['images'].sort(key=lambda x: x.get('exif', {}).get('DateTimeOriginal', ''), reverse=True)

    if is_encrypted:
        gallery_data['manifest_path'] = write_manifest_file(gallery_data)

    # Determine the latest updated timestamp of any files in the source gallery directory
    latest_timestamp = max(os.path.getmtime(os.path.join(gallery_path, f)) for f in os.listdir(gallery_path) if os.path.isfile(os.path.join(gallery_path, f)))
    gallery_data['last_updated'] = datetime.fromtimestamp(latest_timestamp).strftime('%Y:%m:%d %H:%M:%S')

    # Save individual gallery metadata
    gallery_json_output_path = os.path.join(
        config['output_path'], 'metadata', gallery_id, 'index.json'
    )
    os.makedirs(os.path.dirname(gallery_json_output_path), exist_ok=True)
    with open(gallery_json_output_path, 'w') as f:
        json.dump(gallery_data, f, indent=2)

    return gallery_data

def main():
    """
    Process all galleries in the configured source path.
    """
    # Show welcome banner
    title = Text("Gallery Processor", style="bold cyan")
    console.print(Panel(title, border_style="cyan"))

    # Find galleries and count images
    console.print("\n[bold yellow]🔍 Finding galleries...[/]")
    galleries = [g for g in os.listdir(config['source_path']) 
                if os.path.isdir(os.path.join(config['source_path'], g))]
    
    if not galleries:
        console.print("\n[red]❌ No galleries found[/]")
        return

    # Count images in each gallery
    total_images = 0
    gallery_info = []
    
    # Modified gallery information output
    for gallery in galleries:
        metadata_dir = os.path.join(config['output_path'], 'metadata', gallery)
        try:
            image_files = [f for f in os.listdir(metadata_dir)
                          if f.endswith('.json')]
        except FileNotFoundError:
            image_files = []
        num_images = len(image_files)
        if num_images > 0:
            gallery_info.append((gallery, image_files))
            total_images += num_images
            console.print(f"  • [blue]{gallery}[/] → found [green]{num_images} images[/]")
        else:
            console.print(f"  • [blue]{gallery}[/] → [yellow]no images[/]")

    console.print("[bold green]✓[/] Found [bold]{} galleries[/] with [bold]{} total images[/]".format(
        len(galleries), total_images
    ))
    console.print("\n[bold yellow]⚡Processing Galleries:[/]")

    # Process galleries
    success = failed = 0
    galleries_data = {
        "last_updated": datetime.now().isoformat(),
        "galleries": []
    }
    
    for gallery_name, image_files in gallery_info:
        console.print(f"[yellow] →[/] Processing: [bold blue]{gallery_name}[/]")
        try:
            source_path = os.path.join(config['source_path'], gallery_name)
            gallery_data = process_gallery(source_path)
            galleries_data['galleries'].append(gallery_data)
            success += 1
            console.print(f"[green]  ✓[/] Generated: [blue]{gallery_name}/index.json[/]")
            
        except Exception as e:
            failed += 1
            console.print(f"[red]✗ Error processing {gallery_name}: {str(e)}[/]")

    # Write galleries.json
    json_output_path = os.path.join(config['output_path'], 'metadata', 'galleries.json')
    os.makedirs(os.path.dirname(json_output_path), exist_ok=True)
    with open(json_output_path, 'w') as f:
        json.dump(galleries_data, f, indent=2)
    console.print(f"[green]✓[/] Generated main index: [blue]galleries.json[/]")

    # Print summary
    console.print("\n[bold]Processing Summary[/]")
    console.print(f"  [green]✓[/] Processed: [bold]{success}[/] galleries")
    if failed:
        console.print(f"  [red]✗[/] Failed: [bold]{failed}[/] galleries")
        console.print("\n[bold red]⚠️  Some galleries failed to process[/]")
        sys.exit(3)
    else:
        console.print("\n[bold green]✨ All galleries processed successfully![/]")

if __name__ == "__main__":
    main()