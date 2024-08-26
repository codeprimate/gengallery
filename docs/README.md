
# Gengallery

Version 0.1

## Getting Started

1. Copy `config.example.yaml` to `config.yaml` and make changes as desired.
1. Run `pip install -r requirements.txt`

## Usage

1. Create a folder in `galleries`, and add a `gallery.yaml` (See the example gallery)
1. There are optional caption files for images.
1. Run `bin/refresh.py --all` to update entire site, or if run for the first time
1. Run `bin/refresh.py galleryname` to add/refresh that gallery
1. Run `bin/server.py` to start a webserver at http://localhost:8000
1. It is safe to delete anything in `exports` as long as you run `bin/refresh.py --all` afterward

# Copyright

(c)2024 codeprimate under MIT License