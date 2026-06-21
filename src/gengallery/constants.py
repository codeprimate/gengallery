"""Shared literals for CLI, services, and validation (single source of truth)."""

# CLI identity (console script name and help banner)
CLI_APP_NAME = "gengallery"

# Command names (CLI subcommands)
CMD_INIT = "init"
CMD_UPDATE = "update"
CMD_PUSH = "push"
CMD_SERVE = "serve"
CMD_PUSH_SSH = "ssh"
CMD_FACES = "faces"

# Faces subcommands
CMD_FACES_ASSIGN = "assign"
CMD_FACES_UNASSIGN = "unassign"
CMD_FACES_REJECT = "reject"
CMD_FACES_SHOW = "show"
CMD_FACES_MERGE = "merge"
CMD_FACES_RECLUSTER = "recluster"
CMD_FACES_PROPAGATE = "propagate"

# Push provider identifiers (extensible; only ssh is registered in this release)
PUSH_PROVIDER_SSH = "ssh"

# Project layout
CONFIG_FILENAME = "config.yaml"
PACKAGE_JSON_FILENAME = "package.json"
GALLERIES_DIRNAME = "galleries"
TEMPLATES_DIRNAME = "templates"
PUBLIC_HTML_SEGMENT = "public_html"

# Packaged init scaffold (`gengallery.assets.scaffold`)
SCAFFOLD_EXAMPLE_GALLERY_DIRNAME = "example"

# SSH deploy defaults (parity with historical deploy_ssh when keys omitted from config)
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

# Face pipeline: shared model cache (XDG Base Directory; not per-project)
ENV_XDG_CACHE_HOME = "XDG_CACHE_HOME"
XDG_CACHE_APP_DIRNAME = "gengallery"
FACE_MODELS_SUBDIR = "models"
FACE_MODEL_BUNDLE = "buffalo_l"
FACE_MODEL_BUNDLE_VERSION = "insightface-buffalo-l-v1"

IDENTITIES_YAML = "galleries/identities.yaml"

FACES_META_DIR = "faces"  # under export/metadata/
FACES_INDEX_JSON = "index.json"
FACES_IDENTITIES_JSON = "identities.json"
FACES_CLUSTERS_DIR = "clusters"
FACES_CLUSTERS_LATEST_JSON = "clusters/latest.json"
FACES_DETECTIONS_DIR = "detections"
FACES_EMBEDDINGS_DIR = "embeddings"
FACES_CROPS_DIR = "crops"

FACE_SCHEMA_VERSION = 1

# Face config defaults
FACE_DEFAULT_MATCH_THRESHOLD = 0.55
FACE_DEFAULT_CLUSTER_THRESHOLD = 0.45
FACE_DEFAULT_MIN_FACE_SIZE_PX = 40
FACE_DEFAULT_MIN_DETECTION_CONFIDENCE = 0.50
FACE_DEFAULT_AUTO_TAG_PREFIX = "person:"
FACE_DEFAULT_HDBSCAN_MIN_CLUSTER_SIZE = 2

# Face identity slug pattern
FACE_SLUG_PATTERN = r"^[a-z][a-z0-9-]*$"

# Pipeline progress display
PROGRESS_ELLIPSIS = "…"
PROGRESS_FILENAME_MAX_LENGTH = 40
PROGRESS_STAGE_IMAGE_PROCESSING = "Image Processing"
PROGRESS_STAGE_FACE_DETECTION = "Face Detection"
PROGRESS_STAGE_VIDEO_PROCESSING = "Video Processing"
PROGRESS_STAGE_FACE_MATCHING = "Matching identities"
PROGRESS_STAGE_FACE_CLUSTERING = "Clustering faces"
PROGRESS_STAGE_FACE_FINALIZING = "Finalizing face index"

# Face provenance values
FACE_PROVENANCE_POSITIVE = "positive"
FACE_PROVENANCE_NEGATIVE_BLOCKED = "negative_blocked"
FACE_PROVENANCE_PROPAGATED = "propagated"
FACE_PROVENANCE_CLUSTER = "cluster"
FACE_PROVENANCE_UNASSIGNED = "unassigned"
