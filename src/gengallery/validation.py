"""Project structure and config validation for CLI commands."""

from __future__ import annotations

from pathlib import Path

from gengallery.constants import (
    CONFIG_FILENAME,
    PUBLIC_HTML_SEGMENT,
    SSH_DEFAULT_DESTINATION,
    SSH_DEFAULT_GROUP,
    SSH_DEFAULT_HOST,
    SSH_DEFAULT_USER,
)
from gengallery.errors import CliUserError
from gengallery.pathing import load_project_config


def validate_project_root_is_usable_directory(project_root: Path, *, for_init: bool) -> None:
    """
    Ensure ``project_root`` is usable for the given command.

    Non-init: path must exist and be a directory. Init: existing path must be a directory;
    a missing path is allowed (Phase 4 creates it).
    """
    if for_init:
        if project_root.exists() and not project_root.is_dir():
            raise CliUserError(
                f"Project path exists but is not a directory: {project_root}",
            )
        return

    if not project_root.exists():
        raise CliUserError(f"Project directory does not exist: {project_root}")
    if not project_root.is_dir():
        raise CliUserError(f"Project path is not a directory: {project_root}")


def _require_config_str(config: dict, key: str) -> str:
    val = config.get(key)
    if not isinstance(val, str) or not val.strip():
        raise CliUserError(
            f"Invalid or missing non-empty string key {key!r} in {CONFIG_FILENAME}.",
        )
    return val


def validate_existing_project_for_update(project_root: Path) -> dict:
    """
    Load config and ensure layout required by the image/gallery pipeline exists.

    Requires ``source_path`` and ``output_path`` string keys and an existing directory at
    ``project_root / source_path`` (``source_path`` may be relative to the project root).
    """
    config = load_project_config(project_root)
    source_rel = _require_config_str(config, "source_path")
    _require_config_str(config, "output_path")
    source_root = (project_root / Path(source_rel)).resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise CliUserError(
            f"Source gallery directory does not exist: {source_root} "
            f"(from source_path in {CONFIG_FILENAME}).",
        )
    return config


def validate_serve_artifacts(project_root: Path, config: dict) -> Path:
    """
    Resolve ``output_path/public_html`` under ``project_root`` and require it to exist.

    ``output_path`` may be relative to the project root.
    """
    output_rel = _require_config_str(config, "output_path")
    site_root = (project_root / Path(output_rel) / PUBLIC_HTML_SEGMENT).resolve()
    if not site_root.exists() or not site_root.is_dir():
        raise CliUserError(
            f"Generated site directory not found: {site_root}. Run gengallery update first.",
        )
    return site_root


def validate_ssh_config(config: dict) -> dict:
    """
    Validate ``ssh`` section for ``push ssh``.

    ``user``, ``host``, ``destination``, and ``group`` are optional in YAML; defaults match
    legacy ``bin/deploy_ssh.py``. ``post_sync_commands`` is required and must be a non-empty list.
    """
    ssh_raw = config.get("ssh")
    if not isinstance(ssh_raw, dict):
        raise CliUserError(
            f"Missing or invalid 'ssh' mapping in {CONFIG_FILENAME} (required for push ssh).",
        )
    commands = ssh_raw.get("post_sync_commands")
    if not isinstance(commands, list) or len(commands) == 0:
        raise CliUserError(
            f"'ssh.post_sync_commands' in {CONFIG_FILENAME} must be a non-empty list.",
        )
    for i, cmd in enumerate(commands):
        if not isinstance(cmd, str) or not cmd.strip():
            raise CliUserError(
                f"'ssh.post_sync_commands[{i}]' in {CONFIG_FILENAME} must be a non-empty string.",
            )
    return {
        "user": ssh_raw.get("user", SSH_DEFAULT_USER),
        "host": ssh_raw.get("host", SSH_DEFAULT_HOST),
        "destination": ssh_raw.get("destination", SSH_DEFAULT_DESTINATION),
        "group": ssh_raw.get("group", SSH_DEFAULT_GROUP),
        "post_sync_commands": commands,
    }
