#!/usr/bin/env python

import os
import sys
import yaml
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def run_server(port=8000):
    config = load_config()
    export_path = os.path.join(config['output_path'], 'public_html')
    
    if not os.path.isdir(export_path):
        print(f"Error: Export directory '{export_path}' not found.")
        sys.exit(1)

    os.chdir(export_path)
    
    handler = SimpleHTTPRequestHandler
    httpd = HTTPServer(("", port), handler)
    
    print(f"Serving on port {port} from directory: {export_path}")
    print("Press CTRL+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Serve static files from the export directory')
    parser.add_argument('--port', type=int, default=8000,
                       help='Port to run the server on (default: 8000)')
    args = parser.parse_args()
    
    run_server(port=args.port)