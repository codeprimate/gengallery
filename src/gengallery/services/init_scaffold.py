"""Apply packaged scaffold to a project directory (conflict checks then copy)."""

from __future__ import annotations

from pathlib import Path

from gengallery.constants import (
    CONFIG_FILENAME,
    GALLERIES_DIRNAME,
    PACKAGE_JSON_FILENAME,
    TEMPLATES_DIRNAME,
)
from gengallery.errors import CliUserError
from gengallery.services.scaffold_assets import (
    ScaffoldPackagingError,
    ScaffoldTargetExistsError,
    materialize_scaffold,
)

MSG_INIT_CONFLICT_CONFIG = (
    f"Cannot initialize here: {CONFIG_FILENAME} already exists. "
    "Remove it or choose an empty directory."
)
MSG_INIT_CONFLICT_GALLERIES = (
    f"Cannot initialize here: {GALLERIES_DIRNAME!r} exists but is not a directory. "
    "Remove it or choose a different path."
)
MSG_INIT_CONFLICT_TEMPLATES = (
    f"Cannot initialize here: {TEMPLATES_DIRNAME!r} already exists "
    "(file or directory). Remove it or choose an empty directory."
)
MSG_INIT_CONFLICT_PACKAGE_JSON = (
    f"Cannot initialize here: {PACKAGE_JSON_FILENAME} already exists. "
    "Remove it or choose an empty directory."
)


def _ensure_no_init_conflicts(target_root: Path) -> None:
    config_path = target_root / CONFIG_FILENAME
    if config_path.exists() or config_path.is_symlink():
        raise CliUserError(MSG_INIT_CONFLICT_CONFIG)
    galleries_path = target_root / GALLERIES_DIRNAME
    if galleries_path.exists() or galleries_path.is_symlink():
        if not galleries_path.is_dir():
            raise CliUserError(MSG_INIT_CONFLICT_GALLERIES)
    templates_path = target_root / TEMPLATES_DIRNAME
    if templates_path.exists() or templates_path.is_symlink():
        raise CliUserError(MSG_INIT_CONFLICT_TEMPLATES)
    package_json_path = target_root / PACKAGE_JSON_FILENAME
    if package_json_path.exists() or package_json_path.is_symlink():
        raise CliUserError(MSG_INIT_CONFLICT_PACKAGE_JSON)


def run_init(target_root: Path) -> int:
    """
    Copy packaged scaffold into ``target_root``.

    Preconditions:
        ``target_root`` exists and is a directory (the ``init`` command creates missing paths).

    Returns:
        Number of scaffold files written.
    """
    root = target_root.resolve()
    if not root.is_dir():
        raise AssertionError("run_init requires an existing directory")
    _ensure_no_init_conflicts(root)
    try:
        return materialize_scaffold(root, overwrite=False)
    except ScaffoldPackagingError as exc:
        raise CliUserError(str(exc)) from exc
    except ScaffoldTargetExistsError as exc:
        raise CliUserError(
            "Cannot initialize: a file or directory that would be written already exists. "
            f"Details: {exc}"
        ) from exc
