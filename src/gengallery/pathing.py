"""Project root and config path resolution."""

from __future__ import annotations

from pathlib import Path

import yaml

from gengallery.constants import CONFIG_FILENAME
from gengallery.errors import CliUserError


def normalize_cli_project_path(raw: str | None, cwd: Path) -> Path:
    """Resolve project path from CLI (omitted → cwd; relative/absolute segments resolved)."""
    if raw is None:
        return cwd.resolve()
    p = Path(raw)
    joined = p if p.is_absolute() else (cwd / p)
    return joined.resolve()


def project_config_path(project_root: Path) -> Path:
    return project_root / CONFIG_FILENAME


def load_project_config(project_root: Path) -> dict:
    """
    Load ``project_root / config.yaml`` as a YAML mapping.

    Raises:
        CliUserError: missing file, invalid YAML, or YAML that is not a plain mapping.
    """
    path = project_config_path(project_root)
    if not path.is_file():
        raise CliUserError(
            f"Project configuration not found: {path}",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise CliUserError(f"Cannot read configuration file {path}: {e}") from e

    if not text.strip():
        raise CliUserError(f"Configuration file is empty: {path}")

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise CliUserError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(data, dict):
        raise CliUserError(
            f"Configuration must be a YAML mapping (object), not {type(data).__name__}: {path}",
        )
    return data
