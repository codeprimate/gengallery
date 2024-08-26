
# Gengallery

Version 0.1

## Create a static site as simply as possible.

Create folders under `galleries`, add images, create a gallery card.

Then run a single command to generate your site in `export`. Run the included server to demo locally on your browser.

The rest you do is your business.

## Getting Started

1. Copy `config.example.yaml` to `config.yaml` and make changes as desired.
1. Run `pip install -r requirements.txt`

## Usage

1. Create a folder in `galleries`, and add a `gallery.yaml` (See the example gallery in `doc/example_gallery`)
1. There are optional caption files for images.
1. Run `bin/refresh.py --all` to update entire site, or if run for the first time
1. Run `bin/refresh.py galleryname` to add/refresh that gallery
1. Run `bin/serve.py` to start a webserver at http://localhost:8000
1. It is safe to delete anything in `exports` as long as you run `bin/refresh.py --all` afterward

# Copyright

(c)2024 codeprimate under MIT License
