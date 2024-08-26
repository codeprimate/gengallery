#!/usr/bin/env python

import os
import sys
import yaml
from http.server import HTTPServer, SimpleHTTPRequestHandler

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def run_server(port=8000):
    config = load_config()
    export_path = config['output_path']
    
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
    run_server()