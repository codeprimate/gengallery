#!/usr/bin/env python

import os
import sys
import subprocess
import argparse
import yaml

def run_command(command):
    print(f"Running: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip(), flush=True)

    rc = process.poll()
    if rc != 0:
        print(f"Error running {command[0]}:", flush=True)
        print(process.stderr.read(), flush=True)
        sys.exit(1)

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def list_galleries(config):
    galleries = [d for d in os.listdir(config['source_path']) if os.path.isdir(os.path.join(config['source_path'], d))]
    if galleries:
        print("\nAvailable galleries:")
        for gallery in galleries:
            print(f"  - {gallery}")
    else:
        print("\nNo galleries found.")

def refresh(gallery=None, all_galleries=False):
    config = load_config()

    if all_galleries:
        run_command(["python", "bin/image_processor.py", "--all"])
    elif gallery:
        gallery_path = os.path.join(config['source_path'], gallery)
        if not os.path.isdir(gallery_path):
            print(f"Error: Gallery '{gallery}' not found.")
            sys.exit(1)
        run_command(["python", "bin/image_processor.py", gallery])
    else:
        return False

    run_command(["python", "bin/gallery_processor.py"])
    run_command(["python", "bin/generator.py"])
    return True

def main():
    parser = argparse.ArgumentParser(description="Refresh gallery and generate site")
    parser.add_argument("gallery", nargs="?", help="Name of the gallery to refresh")
    parser.add_argument("--all", action="store_true", help="Refresh all galleries")

    args = parser.parse_args()

    if args.all:
        refresh(all_galleries=True)
    elif args.gallery:
        refresh(gallery=args.gallery)
    else:
        parser.print_help()
        config = load_config()
        list_galleries(config)

if __name__ == "__main__":
    main()