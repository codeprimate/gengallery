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
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

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
    if os.path.exists(os.path.join(source_path, image_metadata['filename'])):
        return False
        
    # Remove metadata file
    metadata_path = os.path.join(config['output_path'], 'metadata', gallery_id, f"{image_metadata['id']}.json")
    if os.path.exists(metadata_path):
        os.remove(metadata_path)
        console.print(f"  [yellow]→[/] Removed image metadata: [blue]{metadata_path}[/]")
    
    # Remove processed images
    for size_name in config['image_sizes'].keys():
        output_image_path = os.path.join(
            config['output_path'], 'public_html', 'galleries',
            gallery_id, size_name, f"{image_metadata['id']}.jpg"
        )
        if os.path.exists(output_image_path):
            os.remove(output_image_path)
            console.print(f"  [yellow]→[/] Removed image: [blue]{output_image_path}[/]")
            
    return True

def process_gallery(gallery_path: str) -> dict:
    """
    Process a single gallery directory and generate its metadata.
    """
    gallery_id = os.path.basename(gallery_path)
    
    # Load gallery.yaml
    with open(os.path.join(gallery_path, 'gallery.yaml'), 'r') as f:
        gallery_config = yaml.safe_load(f)

    is_encrypted = gallery_config.get('encrypted', False)

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
    password = gallery_config.get('password', '')
    if password:
        # Generate private gallery ID for password-protected galleries
        private_gallery_id = hashlib.sha256(f"{gallery_id}:{password}".encode('utf-8')).hexdigest()[:16]
        private_gallery_id_hash = hashlib.sha256(private_gallery_id.encode('utf-8')).hexdigest()
        gallery_data['private_gallery_id'] = private_gallery_id
        gallery_data['private_gallery_id_hash'] = private_gallery_id_hash
    else:
        gallery_data['private_gallery_id'] = ''
        gallery_data['private_gallery_id_hash'] = ''

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
        # Try to find cover image by filename first
        cover_image = next(
            (img for img in gallery_data['images'] 
             if img['filename'] == cover_image_filename),
            None
        )
        if cover_image:
            gallery_data['cover'] = {
                "id": cover_image['id'],
                "filename": cover_image['filename'],
                "title": cover_image.get('title', ''),
                "caption": cover_image.get('caption', ''),
                "path": cover_image['cover_path'],
                "thumbnail_path": cover_image['thumbnail_path'],
            }
    
    # Fallback to first image if we have images but no valid cover
    if not gallery_data['cover'] and gallery_data['images']:
        first_image = gallery_data['images'][0]
        gallery_data['cover'] = {
            "id": first_image['id'],
            "filename": first_image['filename'],
            "title": first_image.get('title', ''),
            "caption": first_image.get('caption', ''),
            "path": first_image['cover_path'],
            "thumbnail_path": first_image['thumbnail_path'],
        }

    # Sort images by date taken if available
    gallery_data['images'].sort(key=lambda x: x['exif'].get('DateTimeOriginal', ''), reverse=True)

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