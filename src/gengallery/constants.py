"""Shared literals for CLI, services, and validation (single source of truth)."""

# Command names (CLI subcommands)
CMD_INIT = "init"
CMD_UPDATE = "update"
CMD_PUSH = "push"
CMD_SERVE = "serve"
CMD_PUSH_SSH = "ssh"

# Push provider identifiers (extensible; only ssh is registered in this release)
PUSH_PROVIDER_SSH = "ssh"

# Project layout
CONFIG_FILENAME = "config.yaml"
GALLERIES_DIRNAME = "galleries"
TEMPLATES_DIRNAME = "templates"
PUBLIC_HTML_SEGMENT = "public_html"

# Packaged init scaffold (`gengallery.assets.scaffold`)
SCAFFOLD_EXAMPLE_GALLERY_DIRNAME = "example"

# SSH deploy defaults (parity with legacy bin/deploy_ssh.py when keys omitted from config)
SSH_DEFAULT_USER = "admin"
SSH_DEFAULT_HOST = "gallery.nil42.com"
SSH_DEFAULT_DESTINATION = "/data/gallery/"
SSH_DEFAULT_GROUP = "www-data"

# Serve defaults
DEFAULT_SERVE_PORT = 8000
SERVE_BIND_HOST = "127.0.0.1"
SERVE_PORT_MIN = 1
SERVE_PORT_MAX = 65535

# Process exit codes
EXIT_SUCCESS = 0
EXIT_USER_ERROR = 1
