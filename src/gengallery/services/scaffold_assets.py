"""Read-only packaged scaffold assets for `gengallery init` (CWD-independent)."""

from __future__ import annotations

from collections.abc import Iterable
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from gengallery.constants import CONFIG_FILENAME, TEMPLATES_DIRNAME

ASSETS_PACKAGE = "gengallery.assets"
SCAFFOLD_SUBDIR = "scaffold"


class ScaffoldPackagingError(RuntimeError):
    """Packaged scaffold asset missing or unreadable (check wheel/sdist package-data)."""


class ScaffoldTargetExistsError(FileExistsError):
    """Materialization refused because the target path already exists and overwrite is false."""


def _assets_root() -> Traversable:
    root = files(ASSETS_PACKAGE)
    if not root.is_dir():
        msg = f"package {ASSETS_PACKAGE!r} has no resource directory"
        raise ScaffoldPackagingError(msg)
    return root


def _walk_files(node: Traversable, prefix: str) -> Iterable[tuple[str, Traversable]]:
    """Yield (posix relative path, file traversable) for every file under node."""
    if not node.is_dir():
        return
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        name = child.name
        rel = f"{prefix}/{name}" if prefix else name
        if child.is_dir():
            yield from _walk_files(child, rel)
        elif child.is_file():
            yield (rel, child)


def iter_scaffold_files() -> Iterable[tuple[str, Traversable]]:
    """
    Yield ``(relative_posix_path, traversable)`` for each file that belongs on disk
    after init: ``scaffold/*`` at project root and ``templates/*`` under ``templates/``.
    """
    root = _assets_root()
    scaffold_root = root / SCAFFOLD_SUBDIR
    templates_root = root / TEMPLATES_DIRNAME
    if not scaffold_root.is_dir():
        msg = f"missing packaged directory {SCAFFOLD_SUBDIR!r} under {ASSETS_PACKAGE}"
        raise ScaffoldPackagingError(msg)
    if not templates_root.is_dir():
        msg = f"missing packaged directory {TEMPLATES_DIRNAME!r} under {ASSETS_PACKAGE}"
        raise ScaffoldPackagingError(msg)
    marker = scaffold_root / CONFIG_FILENAME
    if not marker.is_file():
        msg = f"missing packaged scaffold file {CONFIG_FILENAME!r}"
        raise ScaffoldPackagingError(msg)
    yield from _walk_files(scaffold_root, "")
    yield from _walk_files(templates_root, TEMPLATES_DIRNAME)


def materialize_scaffold(target_root: Path, *, overwrite: bool = False) -> None:
    """
    Copy all packaged scaffold files under ``target_root``.

    When ``overwrite`` is false, abort before overwriting an existing file.
    Callers should run project conflict checks (Phase 4.2) before invoking.
    """
    dest_root = target_root.resolve()
    written = 0
    for rel_posix, resource in iter_scaffold_files():
        dest = dest_root / rel_posix
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() or dest.is_symlink():
            if overwrite:
                if dest.is_file() or dest.is_symlink():
                    dest.unlink()
                else:
                    msg = f"refusing to replace non-file path: {dest}"
                    raise ScaffoldTargetExistsError(msg)
            else:
                raise ScaffoldTargetExistsError(str(dest))
        try:
            payload = resource.read_bytes()
        except OSError as exc:
            msg = f"failed to read packaged resource {rel_posix!r}: {exc}"
            raise ScaffoldPackagingError(msg) from exc
        dest.write_bytes(payload)
        written += 1
    if written == 0:
        raise ScaffoldPackagingError("no scaffold files were materialized")
