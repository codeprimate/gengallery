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

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def load_galleries_data(output_path):
    print("*** Loading data...", flush=True)
    galleries_json_path = os.path.join(output_path, 'metadata', 'galleries.json')
    with open(galleries_json_path, 'r') as f:
        return json.load(f)

def markdown_filter(text):
    return markdown.markdown(text)

def generate_tailwind_css():
    print("*** Generating Tailwind CSS...", flush=True)
    input_css = "templates/tailwind/tailwind_input.css"
    output_css = "templates/tailwind/tailwind.css"
    config_file = "templates/tailwind/tailwind.config.js"
    
    subprocess.run([
        "npx", "tailwindcss",
        "-i", input_css,
        "-o", output_css,
        "--config", config_file,
        "--minify"
    ], check=True)
    print("Tailwind CSS generated successfully.", flush=True)

def generate_tag_hash(tag):
    return hashlib.sha256(tag.encode()).hexdigest()[:12]

def generate_gallery_listing_pages(config, galleries_data, output_path, env):
    print("*** Generating gallery listing pages...", flush=True)
    template = env.get_template('index.html.jinja')
    all_tags = set()
    tag_galleries = {}

    for gallery in galleries_data['galleries']:
        for tag in gallery['tags']:
            if gallery['unlisted']:
                continue 
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

        # Copy the 'featured' page to index.html
        if tag == 'featured':
            index_file = os.path.join(output_path, 'public_html', 'index.html')
            shutil.copy2(output_file, index_file)

    print(f"Generated {len(tag_galleries)} tag pages, including 'featured' page copied to index.html.")

def generate_gallery_pages(config, galleries_data, output_path):
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['markdown'] = markdown_filter
    gallery_login_template = env.get_template('gallery_login.html.jinja')
    gallery_template = env.get_template('gallery.html.jinja')
    image_template = env.get_template('image.html.jinja')

    for gallery in galleries_data['galleries']:
        
        context = {
            'site_name': config['site_name'],
            'author': config['author'],
            'gallery': gallery,
            'current_year': datetime.now().year
        }

        # Generate gallery pages
        gallery_dir = os.path.join(output_path, 'public_html', 'galleries', gallery['id'])
        os.makedirs(gallery_dir, exist_ok=True)

        ### Gallery URL obfuscation for password protection
        if gallery['private_gallery_id'] == '':
            gallery_output_filename = 'index.html'
        else:
            # Render the gallery login page as the index page
            gallery_output_filename = f"{gallery['private_gallery_id']}.html"
            gallery_login_rendered_html = gallery_login_template.render(context)
            gallery_login_output_file = os.path.join(gallery_dir, 'index.html')
            with open(gallery_login_output_file, 'w') as f:
                f.write(gallery_login_rendered_html)

        ### Render Gallery page
        gallery_output_file = os.path.join(gallery_dir, gallery_output_filename)
        gallery_rendered_html = gallery_template.render(context)
        with open(gallery_output_file, 'w') as f:
            f.write(gallery_rendered_html)

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

            rendered_image_html = image_template.render(image_context)

            image_output_file = os.path.join(gallery_dir, f"{image['id']}.html")
            with open(image_output_file, 'w') as f:
                f.write(rendered_image_html)

        print(f"*** Generated gallery page and {len(gallery['images'])} image pages for {gallery['title']}")

def generate_404_page(config, output_path):
    print("*** Generating 404 page...", flush=True)
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

def copy_static_files(config, output_path):
    # Create directories if they don't exist
    os.makedirs(os.path.join(output_path, 'public_html', 'css'), exist_ok=True)
    os.makedirs(os.path.join(output_path, 'public_html', 'js'), exist_ok=True)

    # Copy CSS file
    css_src = os.path.join('templates', 'site.css')
    css_dest = os.path.join(output_path, 'public_html', 'css', 'site.css')
    if os.path.exists(css_src):
        shutil.copy2(css_src, css_dest)
        print(f"*** Copied {css_src} to {css_dest}")
    else:
        print(f"Warning: {css_src} not found")

    # Copy JS file
    js_src = os.path.join('templates', 'site.js')
    js_dest = os.path.join(output_path, 'public_html', 'js', 'site.js')
    if os.path.exists(js_src):
        shutil.copy2(js_src, js_dest)
        print(f"*** Copied {js_src} to {js_dest}")
    else:
        print(f"Warning: {js_src} not found")

    # Copy Tailwind CSS file
    tailwind_src = os.path.join('templates', 'tailwind', 'tailwind.css')
    tailwind_dest = os.path.join(output_path, 'public_html', 'css', 'tailwind.css')
    if os.path.exists(tailwind_src):
        shutil.copy2(tailwind_src, tailwind_dest)
        print(f"*** Copied {tailwind_src} to {tailwind_dest}")
    else:
        print(f"Warning: {tailwind_src} not found")

def main():
    config = load_config()
    os.makedirs(os.path.join(config['output_path'], 'public_html'), exist_ok=True)
    os.makedirs(os.path.join(config['output_path'], 'metadata'), exist_ok=True)
    
    generate_tailwind_css()
    
    galleries_data = load_galleries_data(config['output_path'])
    
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['markdown'] = markdown_filter
    env.globals['generate_tag_hash'] = generate_tag_hash
    
    generate_gallery_listing_pages(config, galleries_data, config['output_path'], env)
    generate_gallery_pages(config, galleries_data, config['output_path'])
    generate_404_page(config, config['output_path'])
    copy_static_files(config, config['output_path'])
    print("Gallery listing pages, gallery pages, 404 page generated, and static files copied successfully.")

if __name__ == "__main__":
    main()