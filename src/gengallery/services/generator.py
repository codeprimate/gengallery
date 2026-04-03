#!/usr/bin/env python

import os
import json
import yaml
import shutil
import time
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import markdown
import subprocess
import hashlib
from rich.console import Console

from gengallery.services.pipeline_types import OutputPath, SiteBuildResult
from gengallery.services.site_htpasswd import (
    SITE_HTPASSWD_FILENAME,
    SiteHtpasswdError,
    write_site_htpasswd_from_config,
)

console = Console()
PROTECTED_PAGE_HASH_LENGTH = 16
PROTECTED_PAGE_EXTENSION = '.html'
LEGACY_PROTECTED_PAGE_FILENAME = 'gallery.html'
LISTING_FEATURED_TAG = 'featured'


def _gallery_media_sort_key(item: dict) -> tuple:
    exif = item.get('exif') or {}
    dt = exif.get('DateTimeOriginal') or ''
    return (dt, item.get('id', ''))


def build_gallery_media_timeline(gallery: dict) -> list:
    """Images and videos in one list, reverse chronological by EXIF date (gallery_processor sort)."""
    merged = list(gallery.get('images') or []) + list(gallery.get('videos') or [])
    merged.sort(key=_gallery_media_sort_key, reverse=True)
    return merged


def neighbors_in_timeline(timeline: list, item_id: str) -> tuple:
    """Return (previous_item, next_item) for prev/next arrows across images and videos."""
    for i, item in enumerate(timeline):
        if item.get('id') == item_id:
            prev_item = timeline[i - 1] if i > 0 else None
            next_item = timeline[i + 1] if i < len(timeline) - 1 else None
            return prev_item, next_item
    return None, None

def load_config():
    """Load and parse the YAML configuration file."""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def load_galleries_data(output_path):
    """Load the galleries metadata from JSON."""
    galleries_json_path = os.path.join(output_path, 'metadata', 'galleries.json')
    with open(galleries_json_path, 'r') as f:
        return json.load(f)

def markdown_filter(text):
    """Convert markdown text to HTML."""
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
    """Generate a short hash for a tag name."""
    return hashlib.sha256(tag.encode()).hexdigest()[:12]

def generate_gallery_listing_pages(config, galleries_data, output_path, env) -> dict[str, int]:
    """
    Generate HTML pages for gallery listings, grouped by tags.

    Returns:
        dict mapping tag name to gallery count.
    """
    template = env.get_template('index.html.jinja')
    all_tags = set()
    tag_galleries = {}

    for gallery in galleries_data['galleries']:
        if gallery.get('unlisted', False):
            continue
        is_encrypted = gallery.get('encrypted', False)
        if is_encrypted:
            tags = gallery.get('tags', [])
            if LISTING_FEATURED_TAG not in tags:
                continue
            featured_list = tag_galleries.setdefault(LISTING_FEATURED_TAG, [])
            if any(g.get('id') == gallery.get('id') for g in featured_list):
                continue
            featured_list.append(gallery)
            continue
        for tag in gallery['tags']:
            all_tags.add(tag)
            if tag not in tag_galleries:
                tag_galleries[tag] = []
            tag_galleries[tag].append(gallery)

    for tag, galleries in tag_galleries.items():
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

        if tag == LISTING_FEATURED_TAG:
            index_file = os.path.join(output_path, 'public_html', 'index.html')
            shutil.copy2(output_file, index_file)

    return {tag: len(gals) for tag, gals in tag_galleries.items()}

def get_gallery_templates(env):
    """Get all templates needed for gallery generation."""
    return {
        'login': env.get_template('gallery_login.html.jinja'),
        'gallery': env.get_template('gallery.html.jinja'),
        'encrypted_gallery': env.get_template('encrypted_gallery.html.jinja'),
        'image': env.get_template('image.html.jinja'),
        'encrypted_image': env.get_template('encrypted_image.html.jinja'),
        'video': env.get_template('video.html.jinja'),
        'encrypted_video': env.get_template('encrypted_video.html.jinja'),
    }

def get_gallery_config(gallery):
    """Determine gallery configuration and templates to use."""
    is_encrypted = gallery.get('encrypted', False)
    requires_login = bool(gallery.get('requires_login', False))
    
    if is_encrypted:
        return {
            'output_filename': get_protected_gallery_filename(gallery),
            'needs_login': True,
            'gallery_template': 'encrypted_gallery',
            'image_template': 'encrypted_image',
            'video_template': 'encrypted_video',
        }
    elif requires_login:
        return {
            'output_filename': get_protected_gallery_filename(gallery),
            'needs_login': True,
            'gallery_template': 'gallery',
            'image_template': 'image',
            'video_template': 'video',
        }
    else:
        return {
            'output_filename': 'index.html',
            'needs_login': False,
            'gallery_template': 'gallery',
            'image_template': 'image',
            'video_template': 'video',
        }

def get_protected_gallery_filename(gallery):
    """Build deterministic obfuscated page filename for protected galleries."""
    verifier_hash = gallery.get('storage_token_hash_hex')
    if not verifier_hash or len(verifier_hash) < PROTECTED_PAGE_HASH_LENGTH:
        raise ValueError(
            f"Protected gallery '{gallery.get('id', 'unknown')}' is missing a valid storage_token_hash_hex"
        )

    protected_page_id = verifier_hash[:PROTECTED_PAGE_HASH_LENGTH]
    return f'{protected_page_id}{PROTECTED_PAGE_EXTENSION}'

def generate_login_page(templates, context, gallery_dir):
    """Generate login page for protected galleries."""
    login_html = templates['login'].render(context)
    login_path = os.path.join(gallery_dir, 'index.html')
    os.makedirs(os.path.dirname(login_path), exist_ok=True)
    with open(login_path, 'w') as f:
        f.write(login_html)

def generate_gallery_index(templates, template_key, context, gallery_dir, output_filename):
    """Generate main gallery index page."""
    gallery_html = templates[template_key].render(context)
    output_path = os.path.join(gallery_dir, output_filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(gallery_html)

def remove_legacy_protected_gallery_page(gallery_dir, output_filename):
    """Remove stale legacy protected page so direct legacy URL cannot be used."""
    if output_filename == LEGACY_PROTECTED_PAGE_FILENAME:
        return

    legacy_page_path = os.path.join(gallery_dir, LEGACY_PROTECTED_PAGE_FILENAME)
    if os.path.exists(legacy_page_path):
        os.remove(legacy_page_path)

def generate_image_pages(templates, template_key, gallery, output_path, context):
    """Generate individual image pages for a gallery."""
    timeline = build_gallery_media_timeline(gallery)
    for image in gallery['images']:
        nav_prev, nav_next = neighbors_in_timeline(timeline, image['id'])

        image_context = {
            **context,
            'image': image,
            'nav_prev': nav_prev,
            'nav_next': nav_next,
        }

        rendered_html = templates[template_key].render(image_context)
        output_file = os.path.join(
            output_path,
            'public_html',
            f"galleries/{gallery['id']}/{image['id']}.html"
        )
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(rendered_html)


def generate_video_pages(templates, template_key, gallery, output_path, context):
    """Generate individual video detail pages for a gallery."""
    videos = gallery.get('videos') or []
    timeline = build_gallery_media_timeline(gallery)
    for video in videos:
        nav_prev, nav_next = neighbors_in_timeline(timeline, video['id'])
        video_context = {
            **context,
            'video': video,
            'nav_prev': nav_prev,
            'nav_next': nav_next,
        }
        rendered_html = templates[template_key].render(video_context)
        output_file = os.path.join(
            output_path,
            'public_html',
            f"galleries/{gallery['id']}/{video['id']}.html",
        )
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(rendered_html)


def generate_gallery_pages(config, galleries_data, output_path) -> list[dict]:
    """
    Generate individual gallery and image pages.

    Returns:
        list of gallery summary dicts for each processed gallery.
    """
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['markdown'] = markdown_filter
    
    templates = get_gallery_templates(env)
    gallery_summaries = []

    for gallery in galleries_data['galleries']:
        num_videos = len(gallery.get('videos') or [])
        gallery_config = get_gallery_config(gallery)
        context = {
            'site_name': config['site_name'],
            'author': config['author'],
            'gallery': gallery,
            'current_year': datetime.now().year,
            'protected_gallery_page': gallery_config['output_filename'],
            'media_timeline': build_gallery_media_timeline(gallery),
        }

        gallery_dir = os.path.join(output_path, 'public_html', 'galleries', gallery['id'])
        os.makedirs(gallery_dir, exist_ok=True)

        if gallery_config['needs_login']:
            generate_login_page(templates, context, gallery_dir)

        generate_gallery_index(
            templates,
            gallery_config['gallery_template'],
            context,
            gallery_dir,
            gallery_config['output_filename']
        )
        if gallery_config['needs_login']:
            remove_legacy_protected_gallery_page(gallery_dir, gallery_config['output_filename'])

        generate_image_pages(
            templates,
            gallery_config['image_template'],
            gallery,
            output_path,
            context
        )

        if num_videos > 0:
            generate_video_pages(
                templates,
                gallery_config['video_template'],
                gallery,
                output_path,
                context,
            )

        gallery_summaries.append({
            'title': gallery.get('title', gallery['id']),
            'image_count': len(gallery['images']),
            'video_count': num_videos,
            'is_featured': LISTING_FEATURED_TAG in gallery.get('tags', []),
            'is_encrypted': gallery.get('encrypted', False),
            'is_unlisted': gallery.get('unlisted', False),
        })

    return gallery_summaries

def generate_404_page(config, output_path):
    """Generate the 404 error page."""
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

def copy_static_files(config, output_path) -> list[str]:
    """
    Copy static assets to the public directory.

    Returns:
        list of asset basenames successfully copied.
    """
    os.makedirs(os.path.join(output_path, 'public_html', 'css'), exist_ok=True)
    os.makedirs(os.path.join(output_path, 'public_html', 'js'), exist_ok=True)
    os.makedirs(os.path.join(output_path, 'public_html', 'images'), exist_ok=True)

    files_to_copy = [
        ('templates/site.css', 'public_html/css/site.css'),
        ('templates/site.js', 'public_html/js/site.js'),
        ('templates/tailwind/tailwind.css', 'public_html/css/tailwind.css'),
        ('templates/favicon.ico', 'public_html/favicon.ico'),
        ('templates/robots.txt', 'public_html/robots.txt'),
        ('templates/images/encrypted-listing-cover.svg', 'public_html/images/encrypted-listing-cover.svg'),
    ]

    copied = []
    for src_rel, dest_rel in files_to_copy:
        dest = os.path.join(output_path, dest_rel)
        if os.path.exists(src_rel):
            shutil.copy2(src_rel, dest)
            copied.append(os.path.basename(src_rel))
    return copied

def get_directory_size(path) -> tuple[int, int]:
    """Calculate the total size of a directory in bytes."""
    total_size = 0
    file_count = 0
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if not os.path.islink(file_path):
                total_size += os.path.getsize(file_path)
                file_count += 1
    return total_size, file_count


def run() -> SiteBuildResult:
    """
    Generate the full static site.

    Produces no console output.

    Returns:
        SiteBuildResult with all data needed for the orchestrator to render output.
    """
    t0 = time.time()
    errors: list[dict] = []

    cfg = load_config()
    galleries_data = load_galleries_data(cfg['output_path'])

    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['markdown'] = markdown_filter
    env.globals['generate_tag_hash'] = generate_tag_hash

    tags = generate_gallery_listing_pages(cfg, galleries_data, cfg['output_path'], env)
    gallery_summaries = generate_gallery_pages(cfg, galleries_data, cfg['output_path'])

    generate_404_page(cfg, cfg['output_path'])
    assets_copied: list[str] = []

    try:
        generate_tailwind_css(quiet=True)
        assets_copied.append('tailwind.css')
    except Exception as e:
        errors.append({'stage': 'Tailwind CSS', 'type': type(e).__name__, 'error': str(e)})

    assets_copied.extend(copy_static_files(cfg, cfg['output_path']))

    try:
        htpasswd_status = write_site_htpasswd_from_config(cfg, cfg['output_path'])
        if htpasswd_status == "written":
            assets_copied.append(SITE_HTPASSWD_FILENAME)
    except SiteHtpasswdError as e:
        errors.append({'stage': 'Site .htpasswd', 'type': 'SiteHtpasswdError', 'error': str(e)})

    public_html_path = os.path.join(cfg['output_path'], 'public_html')
    output_paths: list[OutputPath] = []
    path_specs = [
        ("Public HTML", public_html_path),
        ("Galleries", os.path.join(public_html_path, 'galleries')),
        ("CSS", os.path.join(public_html_path, 'css')),
        ("JavaScript", os.path.join(public_html_path, 'js')),
    ]
    for label, path in path_specs:
        if os.path.exists(path):
            size_bytes, file_count = get_directory_size(path)
        else:
            size_bytes, file_count = 0, 0
        output_paths.append(OutputPath(
            label=label,
            path=path,
            file_count=file_count,
            size_bytes=size_bytes,
        ))

    return SiteBuildResult(
        galleries=gallery_summaries,
        tags=tags,
        assets_copied=assets_copied,
        output_paths=output_paths,
        errors=errors,
        elapsed=time.time() - t0,
    )


def main():
    """Entry point for standalone invocation."""
    result = run()

    for gallery in result.galleries:
        flags = []
        if gallery['is_featured']:
            flags.append('⭐')
        if gallery['is_encrypted']:
            flags.append('🔒')
        flag_str = ' '.join(flags)
        img_str = f"{gallery['image_count']} img" if gallery['image_count'] else ''
        vid_str = f"{gallery['video_count']} vid" if gallery['video_count'] else ''
        media = '  ·  '.join(x for x in (img_str, vid_str) if x)
        console.print(f"  [blue]{gallery['title']}[/] {flag_str}  {media}")

    for tag, count in result.tags.items():
        console.print(f"  Tag: {tag} ({count})")

    console.print(f"  Assets: {', '.join(result.assets_copied)}")

    for err in result.errors:
        console.print(f"  [red]✗[/] {err['stage']}: {err['error']}")

    elapsed_str = f"[dim]{result.elapsed:.2f}s[/]"
    if result.errors:
        console.print(f"  [red]Site generation completed with errors[/]  ·  {elapsed_str}")
    else:
        console.print(f"  [green]✨ Site generated successfully[/]  ·  {elapsed_str}")


if __name__ == "__main__":
    main()
