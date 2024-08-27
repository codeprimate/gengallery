#!/usr/bin/env python

import os
import json
import yaml
import shutil
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import markdown

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def load_galleries_data(output_path):
    print("*** Loading data...",flush=True)
    galleries_json_path = os.path.join(output_path, 'galleries', 'galleries.json')
    with open(galleries_json_path, 'r') as f:
        return json.load(f)

def markdown_filter(text):
    return markdown.markdown(text)

def generate_root_index(config, galleries_data, output_path):
    print("*** Generating Index page...",flush=True)
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['markdown'] = markdown_filter
    template = env.get_template('index.html.jinja')

    context = {
        'site_name': config['site_name'],
        'author': config['author'],
        'galleries': galleries_data['galleries'],
        'current_year': datetime.now().year,
        'last_updated': galleries_data['last_updated']
    }

    rendered_html = template.render(context)

    output_file = os.path.join(output_path, 'index.html')
    with open(output_file, 'w') as f:
        f.write(rendered_html)

def generate_gallery_pages(config, galleries_data, output_path):
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['markdown'] = markdown_filter
    gallery_template = env.get_template('gallery.html.jinja')
    image_template = env.get_template('image.html.jinja')

    for gallery in galleries_data['galleries']:
        # Generate gallery page
        context = {
            'site_name': config['site_name'],
            'author': config['author'],
            'gallery': gallery,
            'current_year': datetime.now().year
        }

        rendered_html = gallery_template.render(context)

        gallery_dir = os.path.join(output_path, 'galleries', gallery['id'])
        os.makedirs(gallery_dir, exist_ok=True)
        output_file = os.path.join(gallery_dir, 'index.html')
        with open(output_file, 'w') as f:
            f.write(rendered_html)

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

            image_file = os.path.splitext(image['filename'])[0] + '.html'
            image_output_file = os.path.join(gallery_dir, image_file)
            with open(image_output_file, 'w') as f:
                f.write(rendered_image_html)

        print(f"Generated gallery page and {len(gallery['images'])} image pages for {gallery['title']}")

def copy_static_files(config):
    # Create directories if they don't exist
    os.makedirs(os.path.join(config['output_path'], 'css'), exist_ok=True)
    os.makedirs(os.path.join(config['output_path'], 'js'), exist_ok=True)

    # Copy CSS file
    css_src = os.path.join('templates', 'site.css')
    css_dest = os.path.join(config['output_path'], 'css', 'site.css')
    if os.path.exists(css_src):
        shutil.copy2(css_src, css_dest)
        print(f"*** Copied {css_src} to {css_dest}")
    else:
        print(f"Warning: {css_src} not found")

    # Copy JS file
    js_src = os.path.join('templates', 'site.js')
    js_dest = os.path.join(config['output_path'], 'js', 'site.js')
    if os.path.exists(js_src):
        shutil.copy2(js_src, js_dest)
        print(f"*** Copied {js_src} to {js_dest}")
    else:
        print(f"Warning: {js_src} not found")

def main():
    config = load_config()
    galleries_data = load_galleries_data(config['output_path'])
    generate_root_index(config, galleries_data, config['output_path'])
    generate_gallery_pages(config, galleries_data, config['output_path'])
    copy_static_files(config)
    print("Root index.html, gallery pages generated, and static files copied successfully.")

if __name__ == "__main__":
    main()