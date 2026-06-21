"""gengallery faces — face labeling and identity management subcommands."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from gengallery.constants import (
    EXIT_SUCCESS,
    FACE_DEFAULT_MATCH_THRESHOLD,
)
from gengallery.errors import CliUserError
from gengallery.pathing import load_project_config
from gengallery.services.face_labeling import (
    assign_face,
    load_identities,
    merge_identities,
    reject_face,
    resolve_image_path,
    save_identities,
    unassign_face,
)
from gengallery.services.image_processor import apply_runtime_config

_CONSOLE = Console()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _load_config_and_store(project_root: Path):  # type: ignore[return]
    """Load project config, apply runtime, and return (config, identity_store)."""
    config = load_project_config(project_root)
    apply_runtime_config(config)
    store = load_identities(project_root)
    return config, store


def _detection_for_image(project_root: Path, config: dict, path_str: str) -> tuple[str, str, dict]:
    """Resolve path_str → (gallery_id, filename, detection_record).

    Raises CliUserError if the detection record doesn't exist yet.
    """
    import json

    from gengallery.services.face_processor import _detection_path  # noqa: PLC0415

    gallery_id, filename = resolve_image_path(project_root, config, path_str)
    import hashlib  # noqa: PLC0415

    image_id = hashlib.md5(f"{gallery_id}:{filename}".encode()).hexdigest()[:12]

    import os  # noqa: PLC0415

    os.chdir(project_root)
    det_path = _detection_path(gallery_id, image_id)
    if not det_path.exists():
        raise CliUserError(
            f"No face detection data for {gallery_id}/{filename}.\n"
            "Run 'gengallery update' first to detect faces."
        )
    with det_path.open() as fh:
        det = json.load(fh)
    os.chdir(Path.cwd())  # restore (best-effort)
    return gallery_id, filename, det


# ---------------------------------------------------------------------------
# assign
# ---------------------------------------------------------------------------


def run_assign(project_root: Path, args: argparse.Namespace) -> int:
    """Add positive label(s) for one identity across one or more image paths."""
    slug: str = args.slug
    paths: list[str] = args.paths
    face_index: int | None = args.face

    config, store = _load_config_and_store(project_root)

    import os  # noqa: PLC0415

    os.chdir(project_root)
    try:
        for path_str in paths:
            gallery_id, filename, det = _detection_for_image(project_root, config, path_str)
            faces = det["faces"]

            if not faces:
                raise CliUserError(
                    f"{gallery_id}/{filename} has no detected faces.  Cannot assign."
                )
            if face_index is None and len(faces) > 1:
                raise CliUserError(
                    f"{gallery_id}/{filename} has {len(faces)} faces.  "
                    f"Specify --face N (0-based).  "
                    f"Run 'gengallery faces show {path_str}' to see crops."
                )
            if face_index is not None:
                valid_indices = [f["face_index"] for f in faces]
                if face_index not in valid_indices:
                    raise CliUserError(
                        f"Face index {face_index} not found in {gallery_id}/{filename}.  "
                        f"Valid indices: {valid_indices}"
                    )

            resolved_index = face_index if face_index is not None else (
                None if len(faces) == 1 else face_index
            )
            assign_face(store, slug, gallery_id, filename, resolved_index)
            _CONSOLE.print(
                f"  [green]✓[/green] Assigned [blue]{slug}[/blue] → "
                f"[yellow]{gallery_id}/{filename}[/yellow]"
                + (f" (face {resolved_index})" if resolved_index is not None else "")
            )
    finally:
        os.chdir(Path.cwd())

    save_identities(project_root, store)
    _CONSOLE.print(f"  Saved [dim]{project_root / 'galleries/identities.yaml'}[/dim]")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# unassign
# ---------------------------------------------------------------------------


def run_unassign(project_root: Path, args: argparse.Namespace) -> int:
    """Remove positive label(s) for the given image path(s)."""
    paths: list[str] = args.paths
    face_index: int | None = args.face

    config, store = _load_config_and_store(project_root)

    for path_str in paths:
        gallery_id, filename = resolve_image_path(project_root, config, path_str)
        removed = unassign_face(store, gallery_id, filename, face_index)
        if removed:
            _CONSOLE.print(
                f"  [green]✓[/green] Unassigned [yellow]{gallery_id}/{filename}[/yellow]"
                + (f" (face {face_index})" if face_index is not None else "")
            )
        else:
            _CONSOLE.print(
                f"  [yellow]−[/yellow] No positive found for "
                f"[yellow]{gallery_id}/{filename}[/yellow]"
                + (f" (face {face_index})" if face_index is not None else "")
            )

    save_identities(project_root, store)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------


def run_reject(project_root: Path, args: argparse.Namespace) -> int:
    """Add negative (reject) label(s)."""
    slug: str = args.slug
    paths: list[str] = args.paths
    face_index: int | None = args.face

    config, store = _load_config_and_store(project_root)

    for path_str in paths:
        gallery_id, filename = resolve_image_path(project_root, config, path_str)
        reject_face(store, slug, gallery_id, filename, face_index)
        _CONSOLE.print(
            f"  [green]✓[/green] Rejected [blue]{slug}[/blue] ← "
            f"[yellow]{gallery_id}/{filename}[/yellow]"
            + (f" (face {face_index})" if face_index is not None else "")
        )

    save_identities(project_root, store)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


def run_show(project_root: Path, args: argparse.Namespace) -> int:
    """Print face detections and write crop JPEGs for the given image path(s)."""
    import os  # noqa: PLC0415

    config = load_project_config(project_root)
    apply_runtime_config(config)

    os.chdir(project_root)
    try:
        for path_str in args.paths:
            gallery_id, filename, det = _detection_for_image(project_root, config, path_str)
            faces = det["faces"]

            _CONSOLE.print(f"\n  [bold]{gallery_id}/{filename}[/bold]  "
                           f"[dim]{len(faces)} face(s)[/dim]")

            if not faces:
                continue

            from gengallery.services.face_processor import write_crops_for_image  # noqa: PLC0415

            source_path = config.get("source_path", "galleries")
            image_path = str(Path(source_path) / gallery_id / filename)
            import hashlib  # noqa: PLC0415

            image_id = hashlib.md5(f"{gallery_id}:{filename}".encode()).hexdigest()[:12]
            written = write_crops_for_image(image_path, gallery_id, image_id)

            for face in faces:
                bbox_str = ", ".join(f"{v:.3f}" for v in face["bbox"])
                identity_str = face.get("identity_id") or "[dim]unassigned[/dim]"
                prov_str = face.get("provenance", "unassigned")
                conf_str = f"{face['detection_confidence']:.3f}"
                _CONSOLE.print(
                    f"    face {face['face_index']:>2}  "
                    f"bbox=[{bbox_str}]  "
                    f"conf={conf_str}  "
                    f"identity={identity_str}  "
                    f"prov={prov_str}"
                )

            if written:
                _CONSOLE.print("    [dim]Crops written:[/dim]")
                for p in written:
                    _CONSOLE.print(f"      {p}")
    finally:
        os.chdir(Path.cwd())

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def run_merge(project_root: Path, args: argparse.Namespace) -> int:
    """Merge source identity into target identity."""
    source_slug: str = args.source_slug
    target_slug: str = args.target_slug

    _config, store = _load_config_and_store(project_root)
    merge_identities(store, source_slug, target_slug)
    save_identities(project_root, store)

    _CONSOLE.print(
        f"  [green]✓[/green] Merged [blue]{source_slug}[/blue] → "
        f"[blue]{target_slug}[/blue].  "
        f"Run [dim]gengallery update[/dim] to propagate."
    )
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# recluster
# ---------------------------------------------------------------------------


def run_recluster(project_root: Path, args: argparse.Namespace) -> int:
    """Drop anonymous cluster assignments and rerun clustering."""
    import os  # noqa: PLC0415

    config = load_project_config(project_root)
    apply_runtime_config(config)
    os.chdir(project_root)
    try:
        from gengallery.services.face_processor import recluster  # noqa: PLC0415

        placed = recluster()
    finally:
        os.chdir(Path.cwd())

    _CONSOLE.print(f"  [green]✓[/green] Recluster complete — {placed} faces placed in clusters.")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# propagate
# ---------------------------------------------------------------------------


def run_propagate(project_root: Path, args: argparse.Namespace) -> int:
    """Run propagation without a full update.  Optional --dry-run."""
    dry_run: bool = args.dry_run
    identity_filter: str | None = getattr(args, "identity", None)

    import os  # noqa: PLC0415

    config = load_project_config(project_root)
    apply_runtime_config(config)
    os.chdir(project_root)
    try:
        from gengallery.services.face_processor import propagate  # noqa: PLC0415

        changes = propagate(dry_run=dry_run, identity_filter=identity_filter)
    finally:
        os.chdir(Path.cwd())

    action = "[dim](dry run)[/dim] would change" if dry_run else "changed"
    _CONSOLE.print(f"  Propagation {action} [green]{len(changes)}[/green] face assignment(s).")

    match_threshold = config.get("faces", {}).get("match_threshold", FACE_DEFAULT_MATCH_THRESHOLD)
    for ch in changes:
        _CONSOLE.print(
            f"    {ch['gallery']}/{ch['filename']} face={ch['face_index']}  "
            f"{ch['old_identity'] or 'unassigned'} → {ch['new_identity'] or 'unassigned'}  "
            f"[dim]{ch.get('match_score') or ''}[/dim]"
        )

    if dry_run and changes:
        _CONSOLE.print(
            f"\n  [dim]Re-run without --dry-run to persist.  "
            f"Raise threshold (current: {match_threshold}) to reduce false positives.[/dim]"
        )

    return EXIT_SUCCESS
