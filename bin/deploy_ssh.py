#!/usr/bin/env python

import os
import sys
import yaml
import subprocess
from pathlib import Path

def load_config():
    """Load configuration from YAML file."""
    config_file = Path("config.yaml")
    if not config_file.exists():
        config_file = Path("config.example.yaml")
    
    if not config_file.exists():
        sys.exit("Error: No config.yaml or config.example.yaml found")
        
    with open(config_file) as f:
        return yaml.safe_load(f)

def run_command(command, check=True):
    """Execute a shell command and handle errors."""
    try:
        subprocess.run(command, check=check, shell=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"Command failed with exit code {e.returncode}: {command}")

def deploy(config):
    """Deploy the site using rsync and SSH."""
    # Build paths
    source_path = Path(config['output_path']) / "public_html/"
    
    # Get SSH config with defaults
    ssh_config = config.get('ssh', {})
    user = ssh_config.get('user', 'admin')
    host = ssh_config.get('host', 'gallery.nil42.com')
    destination = ssh_config.get('destination', '/data/gallery/')
    group = ssh_config.get('group', 'www-data')
    
    # Construct SSH host string
    ssh_host = f"{user}@{host}"
    
    # Ensure source directory exists
    if not source_path.exists():
        sys.exit(f"Error: Source directory not found: {source_path}")
    
    # Construct and run rsync command
    rsync_cmd = f'rsync -avz --delete "{source_path}/" "{ssh_host}:{destination}"'
    print(f"Running: {rsync_cmd}")
    run_command(rsync_cmd)
    
    # Run post-sync commands
    for cmd in ssh_config['post_sync_commands']:
        formatted_cmd = cmd.format(
            user=user,
            group=group,
            destination=destination
        )
        ssh_cmd = f'ssh {ssh_host} "{formatted_cmd}"'
        print(f"Running: {ssh_cmd}")
        run_command(ssh_cmd)

def main():
    config = load_config()
    deploy(config)

if __name__ == "__main__":
    main() 