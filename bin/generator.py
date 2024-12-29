#!/usr/bin/env python

import os
import json
import yaml
import shutil
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import markdown
import subprocess
import hashlib
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

console = Console()

def load_config():
    """Load and parse the YAML configuration file.

    Returns:
        dict: The parsed configuration data.
    """
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def load_galleries_data(output_path):
    """Load the galleries metadata from JSON.

    Args:
        output_path (str): Path to the directory containing metadata.

    Returns:
        dict: The parsed galleries data.
    """
    galleries_json_path = os.path.join(output_path, 'metadata', 'galleries.json')
    with open(galleries_json_path, 'r') as f:
        return json.load(f)

def markdown_filter(text):
    """Convert markdown text to HTML.

    Args:
        text (str): Markdown-formatted text.

    Returns:
        str: HTML-formatted text.
    """
    return markdown.markdown(text)

def generate_tailwind_css(quiet=False):
    """Generate minified Tailwind CSS from input file using npx."""
    subprocess.run([
        "npx", "tailwindcss",
        "-i", "templates/tailwind/tailwind_input.css",
        "-o", "templates/tailwind/tailwind.css",
        "--config", "templates/tailwind/tailwind.config.js",
        "--minify"
    ], check=True, capture_output=quiet)

def generate_tag_hash(tag):
    """Generate a short hash for a tag name.

    Args:
        tag (str): The tag to hash.

    Returns:
        str: A 12-character hexadecimal hash of the tag.
    """
    return hashlib.sha256(tag.encode()).hexdigest()[:12]

def generate_gallery_listing_pages(config, galleries_data, output_path, env, progress=None, task=None):
    """Generate HTML pages for gallery listings, grouped by tags."""
    if progress:
        progress.update(task, description="[yellow]Generating tag listing pages")
    
    template = env.get_template('index.html.jinja')
    all_tags = set()
    tag_galleries = {}

    # First pass - collect tags and galleries
    for gallery in galleries_data['galleries']:
        is_encrypted = gallery.get('encrypted', False)
        is_unlisted = gallery.get('unlisted', False)
        if is_encrypted or is_unlisted:
            continue
        for tag in gallery['tags']:
            all_tags.add(tag)
            if tag not in tag_galleries:
                tag_galleries[tag] = []
            tag_galleries[tag].append(gallery)

    if progress:
        progress.update(task, total=len(tag_galleries))

    # Add summary output
    console.print("[yellow]📑 Tag pages:[/yellow]")
    for tag, galleries in sorted(tag_galleries.items()):
        console.print(f"[yellow]→[/yellow] [blue]{tag}[/blue] ({len(galleries)} galleries)")
        
        tag_hash = generate_tag_hash(tag)
        output_file = os.path.join(output_path, 'public_html', f'{tag_hash}.html')
        relative_path = os.path.join('public_html', f'{tag_hash}.html')
        console.print(f"  [green]✓[/green] Index page: [blue]{relative_path}[/blue]")

    for tag, galleries in tag_galleries.items():
        if progress:
            progress.update(task, description=f"[yellow]Processing tag: {tag}")

        context = {
            'site_name': config['site_name'],
            'author': config['author'],
            'galleries': galleries,
            'current_year': datetime.now().year,
            'last_updated': galleries_data['last_updated'],
            'tag': tag,
            'all_tags': sorted(list(all_tags)),
            'page_title': tag
        }

        rendered_html = template.render(context)
        
        tag_hash = generate_tag_hash(tag)
        output_file = os.path.join(output_path, 'public_html', f'{tag_hash}.html')
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(rendered_html)

        # Copy the 'featured' page to index.html
        if tag == 'featured':
            index_file = os.path.join(output_path, 'public_html', 'index.html')
            shutil.copy2(output_file, index_file)

        if progress and task:
            progress.advance(task)

def generate_gallery_pages(config, galleries_data, output_path, progress=None, task=None):
    """Generate individual gallery and image pages.

    Handles generation of regular, password-protected, and encrypted galleries,
    including their login pages and individual image pages.

    Args:
        config (dict): Site configuration data.
        galleries_data (dict): Gallery metadata.
        output_path (str): Base output directory path.
    """
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['markdown'] = markdown_filter
    
    # Load all required templates
    gallery_login_template = env.get_template('gallery_login.html.jinja')
    gallery_template = env.get_template('gallery.html.jinja')
    encrypted_gallery_template = env.get_template('encrypted_gallery.html.jinja')
    image_template = env.get_template('image.html.jinja')
    encrypted_image_template = env.get_template('encrypted_image.html.jinja')

    for gallery in galleries_data['galleries']:
        if progress:
            progress.update(task, description=f"[yellow]Gallery: [cyan]{gallery['title']}[/cyan] ({len(gallery['images'])} images)")
        else:
            # Build status icons
            status_icons = []
            if 'featured' in gallery.get('tags', []):
                status_icons.append("[yellow]⭐[/]")
            if gallery.get('unlisted', False):
                status_icons.append("[yellow]🕶[/]")
            if gallery.get('private_gallery_id', ''):
                status_icons.append("[red]🔑[/]")
            if gallery.get('encrypted', False):
                status_icons.append("[red]🔒[/]")
            status_str = " ".join(status_icons)
            
            console.print(f"[yellow]→[/yellow] [blue]{gallery['title']}[/blue] {status_str} ({len(gallery['images'])} images)")

        # Modify encrypted gallery handling
        is_encrypted = gallery.get('encrypted', False)
        # if is_encrypted:
        #     # Instead of sanitizing, add encrypted-specific fields
        #     encrypted_basename = hashlib.sha256(f"{gallery['private_gallery_id']}:{gallery['cover']['filename']}".encode()).hexdigest()[:16]
        #     gallery['cover']['encrypted_filename'] = encrypted_basename
            
        #     # Add encrypted filename to each image
        #     for image in gallery['images']:
        #         encrypted_basename = hashlib.sha256(f"{gallery['private_gallery_id']}:{image['filename']}".encode()).hexdigest()[:16]
        #         image['encrypted_filename'] = encrypted_basename

        context = {
            'site_name': config['site_name'],
            'author': config['author'],
            'gallery': gallery,
            'current_year': datetime.now().year
        }

        # Generate gallery pages
        gallery_dir = os.path.join(output_path, 'public_html', 'galleries', gallery['id'])
        os.makedirs(gallery_dir, exist_ok=True)

        ### Handle different gallery types
        has_password = bool(gallery.get('private_gallery_id', ''))
        
        if is_encrypted:
            gallery_output_filename = f"{gallery['private_gallery_id']}.html"
            gallery_template_to_use = encrypted_gallery_template
            image_template_to_use = encrypted_image_template
            
            # Generate login page
            gallery_login_rendered_html = gallery_login_template.render(context)
            gallery_login_output_file = os.path.join(gallery_dir, 'index.html')
            with open(gallery_login_output_file, 'w') as f:
                f.write(gallery_login_rendered_html)
                
        elif has_password:
            gallery_output_filename = f"{gallery['private_gallery_id']}.html"
            gallery_template_to_use = gallery_template
            image_template_to_use = image_template
            
            # Generate login page
            gallery_login_rendered_html = gallery_login_template.render(context)
            gallery_login_output_file = os.path.join(gallery_dir, 'index.html')
            with open(gallery_login_output_file, 'w') as f:
                f.write(gallery_login_rendered_html)
                
        else:
            gallery_output_filename = 'index.html'
            gallery_template_to_use = gallery_template
            image_template_to_use = image_template

        ### Render Gallery page
        gallery_output_file = os.path.join(gallery_dir, gallery_output_filename)
        gallery_rendered_html = gallery_template_to_use.render(context)
        with open(gallery_output_file, 'w') as f:
            f.write(gallery_rendered_html)
            
        # Add status line for gallery index page
        if is_encrypted or has_password:
            console.print(f"  [green]✓[/green] Login page: [blue]galleries/{gallery['id']}/index.html[/blue]")
            console.print(f"  [green]✓[/green] Index page: [blue]galleries/{gallery['id']}/{gallery_output_filename}[/blue]")
        else:
            console.print(f"  [green]✓[/green] Index page: [blue]galleries/{gallery['id']}/index.html[/blue]")

        # Generate individual image pages
        for i, image in enumerate(gallery['images']):
            prev_image = gallery['images'][i-1] if i > 0 else None
            next_image = gallery['images'][i+1] if i < len(gallery['images'])-1 else None

            image_context = {
                'site_name': config['site_name'],
                'author': config['author'],
                'gallery': gallery,
                'image': image,
                'prev_image': prev_image,
                'next_image': next_image,
                'current_year': datetime.now().year
            }

            rendered_image_html = image_template_to_use.render(image_context)
            
            # Use the path from metadata to construct the output file path
            # Remove leading slash and add .html extension if not present
            output_file = os.path.join(
                output_path, 
                'public_html', 
                f"galleries/{gallery['id']}/{image['id']}.html"
            )
            
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w') as f:
                f.write(rendered_image_html)

        console.print(f"  [green]✓ {len(gallery['images'])}[/green] image pages")

        if progress and task:
            progress.advance(task)

def generate_404_page(config, output_path, progress=None, task=None):
    """Generate the 404 error page.

    Args:
        config (dict): Site configuration data.
        output_path (str): Base output directory path.
    """
    if progress:
        progress.update(task, description="[yellow]Generating 404 page")
    
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('404.html.jinja')

    context = {
        'site_name': config['site_name'],
        'author': config['author'],
        'current_year': datetime.now().year
    }

    rendered_html = template.render(context)

    output_file = os.path.join(output_path, 'public_html', '404.html')
    with open(output_file, 'w') as f:
        f.write(rendered_html)

def copy_static_files(config, output_path, quiet=False, progress=None, task=None):
    """Copy static assets to the public directory."""
    if progress:
        progress.update(task, description="[yellow]Copying static files")
    
    # Create directories if they don't exist
    os.makedirs(os.path.join(output_path, 'public_html', 'css'), exist_ok=True)
    os.makedirs(os.path.join(output_path, 'public_html', 'js'), exist_ok=True)

    files_to_copy = [
        ('templates/site.css', 'public_html/css/site.css'),
        ('templates/site.js', 'public_html/js/site.js'),
        ('templates/tailwind/tailwind.css', 'public_html/css/tailwind.css'),
        ('templates/favicon.ico', 'public_html/favicon.ico'),
        ('templates/robots.txt', 'public_html/robots.txt')
    ]

    for src_rel, dest_rel in files_to_copy:
        src = os.path.join(src_rel)
        dest = os.path.join(output_path, dest_rel)
        
        if os.path.exists(src):
            shutil.copy2(src, dest)
            if not quiet:
                console.print(f"[green]✓[/green] Copied [blue]{os.path.basename(src)}[/blue]")
        else:
            if not quiet:
                console.print(f"[yellow]⚠[/yellow] {os.path.basename(src)} not found")

def get_directory_size(path):
    """Calculate the total size of a directory in bytes.

    Args:
        path (str): Path to the directory

    Returns:
        tuple: (total_size, file_count)
    """
    total_size = 0
    file_count = 0
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if not os.path.islink(file_path):
                total_size += os.path.getsize(file_path)
                file_count += 1
    return total_size, file_count

def main():
    """Main entry point for the static site generator."""
    title = Text("Gallery Site Generator", style="bold cyan")
    console.print(Panel(title, border_style="cyan"))

    start_time = datetime.now()
    stage_times = {}
    errors = []
    any_errors = False

    try:
        # Stage 1: Load Configuration
        console.print("\n[bold blue]Stage 1: Loading configuration...[/bold blue]")
        stage_start = datetime.now()
        config = load_config()
        galleries_data = load_galleries_data(config['output_path'])
        stage_times['load'] = datetime.now() - stage_start
        console.print(f"[green]✓[/green] [dim]Configuration loaded in {stage_times['load'].total_seconds():.1f}s[/dim]")

        # Show gallery summary
        console.print("\n[yellow]🔍 Found galleries:[/yellow]")
        for gallery in galleries_data['galleries']:
            num_images = len(gallery['images'])
            status = []
            if gallery.get('encrypted', False):
                status.append("[red]🔒[/]")
            if gallery.get('unlisted', False):
                status.append("[yellow]👁[/]")
            status_str = " ".join(status)
            console.print(f"  • [blue]{gallery['title']}[/] → [green]{num_images}[/] images {status_str}")

        console.print(f"\n[green]✓ Total: {len(galleries_data['galleries'])} galleries[/]")

        env = Environment(loader=FileSystemLoader('templates'))
        env.filters['markdown'] = markdown_filter
        env.globals['generate_tag_hash'] = generate_tag_hash

        # Stage 2: Generate Tag Listings
        console.print("\n[bold blue]Stage 2: Generating tag listings...[/bold blue]")
        stage_start = datetime.now()
        generate_gallery_listing_pages(config, galleries_data, config['output_path'], env)
        stage_times['tags'] = datetime.now() - stage_start
        console.print(f"[green]✓[/green] [dim]Completed in {stage_times['tags'].total_seconds():.1f}s[/dim]")

        # Stage 3: Generate Gallery Pages
        console.print("\n[bold blue]Stage 3: Generating gallery pages...[/bold blue]")
        stage_start = datetime.now()
        generate_gallery_pages(config, galleries_data, config['output_path'])
        stage_times['galleries'] = datetime.now() - stage_start
        console.print(f"[green]✓[/green] [dim]Completed in {stage_times['galleries'].total_seconds():.1f}s[/dim]")

        # Stage 4: Finalizing site...
        console.print("\n[bold blue]Stage 4: Finalizing site...[/bold blue]")
        stage_start = datetime.now()
        
        try:
            generate_tailwind_css(quiet=True)
            console.print(f"[green]✓[/green] Generated [blue]Tailwind CSS[/blue]")
        except Exception as e:
            any_errors = True
            errors.append({
                'stage': 'Tailwind CSS Generation',
                'type': type(e).__name__,
                'error': str(e)
            })
            console.print("[red]✗[/red] Failed to generate Tailwind CSS")

        generate_404_page(config, config['output_path'])
        copy_static_files(config, config['output_path'], quiet=False)
        stage_times['finalize'] = datetime.now() - stage_start
        console.print(f"[green]✓[/green] [dim]Completed in {stage_times['finalize'].total_seconds():.1f}s[/dim]")

    except Exception as e:
        any_errors = True
        errors.append({
            'stage': 'General',
            'type': type(e).__name__,
            'error': str(e)
        })

    # Print Build Summary
    duration = datetime.now() - start_time
    console.print("\n[bold]Build Summary[/bold]")
    console.print(f"Duration: {duration.total_seconds():.1f} seconds")

    # Directory statistics
    public_html_path = os.path.join(config['output_path'], 'public_html')
    total_size, file_count = get_directory_size(public_html_path)
    
    # Output paths table
    paths_table = Table(title="\nOutput Paths")
    paths_table.add_column("Type", style="cyan")
    paths_table.add_column("Path", style="yellow")
    paths_table.add_column("Status", style="green")
    paths_table.add_column("Files", style="blue", justify="right")
    paths_table.add_column("Size", style="magenta", justify="right")
    
    paths = [
        ("Base Output", config['output_path']),
        ("Public HTML", public_html_path),
        ("Galleries", os.path.join(public_html_path, 'galleries')),
        ("CSS", os.path.join(public_html_path, 'css')),
        ("JavaScript", os.path.join(public_html_path, 'js')),
    ]
    
    for path_type, path in paths:
        exists = os.path.exists(path)
        status = "[green]✓[/]" if exists else "[red]✗[/]"
        
        if exists:
            dir_size, file_count = get_directory_size(path)
            size_str = f"{dir_size / (1024*1024):.1f} MB"
            files_str = f"{file_count:,}"
        else:
            size_str = "-"
            files_str = "-"
            
        paths_table.add_row(
            path_type,
            path,
            status,
            files_str,
            size_str
        )
    
    console.print(paths_table)

    if any_errors:
        error_table = Table(title="\nBuild Errors")
        error_table.add_column("Stage", style="cyan")
        error_table.add_column("Type", style="magenta")
        error_table.add_column("Error", style="red", no_wrap=False)
        
        for error in errors:
            error_table.add_row(
                error['stage'],
                error.get('type', 'Unknown'),
                error.get('error', 'Unknown error')
            )
        
        console.print(error_table)
        console.print("\n[red]Build failed[/red]")
    else:
        console.print("\n[bold green]✨ Site generated successfully![/bold green]")

if __name__ == "__main__":
    main()