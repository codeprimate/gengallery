"""Face pipeline stage: detect, embed, label, propagate, cluster, and auto-tag.

Mirrors image_processor / video_processor conventions:
  - Module-level ``config: dict = {}`` shared via apply_runtime_config().
  - ``discover_galleries() -> dict[str, int]``
  - ``run() -> FaceStageResult``

Pipeline algorithm
------------------
Per image (incremental):
  Load oriented image → detect faces → embed each → write detection JSON + embedding bins

Then (full pass even if all images skipped):
  Load identities.yaml
  Apply positives → provenance=positive
  Apply negatives → block map
  Propagate → provenance=propagated / unassigned
  Cluster remaining unassigned → provenance=cluster / id_unnamed_*
  Update centroids
  Write clusters/latest.json, index.json under galleries/_metadata
  Export faces[] onto export/metadata/{gallery}/{image_id}.json
  Sync person:* auto-tags into sidecar YAMLs
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image
from rich.console import Console

from gengallery.constants import (
    FACE_DEFAULT_AUTO_TAG_PREFIX,
    FACE_DEFAULT_CLUSTER_THRESHOLD,
    FACE_DEFAULT_HDBSCAN_MIN_CLUSTER_SIZE,
    FACE_DEFAULT_MATCH_THRESHOLD,
    FACE_DEFAULT_MIN_DETECTION_CONFIDENCE,
    FACE_DEFAULT_MIN_FACE_SIZE_PX,
    FACE_MODEL_BUNDLE_VERSION,
    FACE_PROVENANCE_NEGATIVE_BLOCKED,
    FACE_PROVENANCE_POSITIVE,
    FACE_PROVENANCE_UNASSIGNED,
    FACE_SCHEMA_VERSION,
    FACES_CLUSTERS_LATEST_JSON,
    FACES_CROPS_DIR,
    FACES_DETECTIONS_DIR,
    FACES_EMBEDDINGS_DIR,
    FACES_INDEX_JSON,
    EXPORT_IMAGE_FACES_FIELD,
    GALLERIES_DIRNAME,
    GALLERIES_METADATA_DIR,
    IDENTITIES_YAML,
    PROGRESS_STAGE_FACE_CLUSTERING,
    PROGRESS_STAGE_FACE_DETECTION,
    PROGRESS_STAGE_FACE_FINALIZING,
    PROGRESS_STAGE_FACE_MATCHING,
)
from gengallery.services.gallery_paths import is_source_gallery_dirname
from gengallery.services.face_labeling import (
    FaceRef,
    IdentityStore,
    load_identities,
)
from gengallery.services.face_matching import (
    build_exemplar_map,
    build_negative_map,
    cluster_unassigned,
    compute_centroids,
    propagate_identities,
)
from gengallery.services.face_models import (
    analyze_image,
    get_face_analyzer,
    load_embedding,
    model_bundle_version,
    save_embedding,
)

# Shared runtime config (populated by apply_runtime_config via image_processor)
from gengallery.services.image_processor import (
    SUPPORTED_FORMATS,
    config,
    rotate_image,
)
from gengallery.services.pipeline_types import FaceStageResult
from gengallery.services.progress_display import (
    create_file_progress,
    set_file_task_description,
    set_phase_task_description,
)

warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)

console = Console()

# Maximum image dimension fed to the detector (speed / accuracy trade-off)
_DETECT_MAX_DIM = 1024
# JPEG quality for written crop images
_CROP_JPEG_QUALITY = 85


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _gallery_metadata_dir() -> Path:
    """Absolute path to galleries/_metadata (embeddings, detections, crops)."""
    return Path(config["source_path"]) / GALLERIES_METADATA_DIR


def _legacy_export_face_dir() -> Path:
    """Pre-move face cache location under export/metadata/faces."""
    return Path(config["output_path"]) / "metadata" / "faces"


def _migrate_legacy_face_metadata() -> None:
    """Move export/metadata/faces to galleries/_metadata when upgrading layout."""
    legacy = _legacy_export_face_dir()
    target = _gallery_metadata_dir()
    if not legacy.is_dir() or target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy), str(target))


def _detection_path(gallery_id: str, image_id: str) -> Path:
    return _gallery_metadata_dir() / FACES_DETECTIONS_DIR / gallery_id / f"{image_id}.json"


def _embedding_path(face_id: str) -> Path:
    return _gallery_metadata_dir() / FACES_EMBEDDINGS_DIR / f"{face_id}.bin"


def _crop_path(gallery_id: str, image_stem: str, face_index: int) -> Path:
    return _gallery_metadata_dir() / FACES_CROPS_DIR / gallery_id / f"{image_stem}_{face_index}.jpg"


def _export_image_metadata_path(gallery_id: str, image_id: str) -> Path:
    return Path(config["output_path"]) / "metadata" / gallery_id / f"{image_id}.json"


def _identities_yaml_path() -> Path:
    return Path(config.get("source_path", GALLERIES_DIRNAME)).parent / IDENTITIES_YAML


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_galleries() -> dict[str, int]:
    """Return {gallery_id: image_count} for all galleries that have at least one image."""
    source = config["source_path"]
    result: dict[str, int] = {}
    for gallery in sorted(os.listdir(source)):
        if not is_source_gallery_dirname(gallery):
            continue
        if not os.path.isdir(os.path.join(source, gallery)):
            continue
        gallery_path = os.path.join(source, gallery)
        images = [
            f for f in os.listdir(gallery_path) if f.lower().endswith(SUPPORTED_FORMATS)
        ]
        if images:
            result[gallery] = len(images)
    return result


# ---------------------------------------------------------------------------
# Face ID computation
# ---------------------------------------------------------------------------


def _face_id(gallery_id: str, image_id: str, face_index: int) -> str:
    raw = f"{gallery_id}:{image_id}:{face_index}:{model_bundle_version()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Incremental skip
# ---------------------------------------------------------------------------


def _source_mtimes() -> list[float]:
    """Return list of relevant source-side file mtimes for skip comparisons."""
    mtimes = [os.path.getmtime("config.yaml")]
    iy = Path(IDENTITIES_YAML)
    if iy.exists():
        mtimes.append(os.path.getmtime(iy))
    return mtimes


def _detection_is_fresh(detection_path: Path, image_mtime: float, base_mtimes: list[float]) -> bool:
    """Return True if the detection JSON exists and is newer than all source files."""
    if not detection_path.exists():
        return False
    det_mtime = os.path.getmtime(detection_path)
    return det_mtime >= max(base_mtimes + [image_mtime])


# ---------------------------------------------------------------------------
# Image loading (EXIF-oriented)
# ---------------------------------------------------------------------------


def _load_oriented_rgb(image_path: str) -> tuple[np.ndarray, int, int]:
    """Load image, apply EXIF rotation, return (HxWx3 uint8 RGB, width, height)."""
    with Image.open(image_path) as img:
        # Apply EXIF orientation
        exif_data = img.getexif()
        orientation = exif_data.get(274, 1)  # tag 274 = Orientation
        img = rotate_image(img, orientation)
        img = img.convert("RGB")
        width, height = img.size
        arr = np.array(img, dtype=np.uint8)
    return arr, width, height


def _resize_for_detection(
    arr: np.ndarray, max_dim: int
) -> tuple[np.ndarray, float]:
    """Resize image so longest side ≤ max_dim.  Returns (resized_array, scale_factor)."""
    h, w = arr.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return arr, 1.0
    scale = max_dim / longest
    new_w, new_h = int(w * scale), int(h * scale)
    import cv2  # type: ignore[import-untyped]
    resized = cv2.resize(arr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale


# ---------------------------------------------------------------------------
# bbox normalisation
# ---------------------------------------------------------------------------


def _bbox_normalised(x1: float, y1: float, x2: float, y2: float, w: int, h: int) -> list[float]:
    """Convert pixel bbox [x1,y1,x2,y2] to normalised [x, y, width, height]."""
    nx = max(0.0, x1 / w)
    ny = max(0.0, y1 / h)
    nw = min(1.0, (x2 - x1) / w)
    nh = min(1.0, (y2 - y1) / h)
    return [round(nx, 6), round(ny, 6), round(nw, 6), round(nh, 6)]


# ---------------------------------------------------------------------------
# Detection JSON
# ---------------------------------------------------------------------------


def _load_detection(gallery_id: str, image_id: str) -> dict[str, Any] | None:
    p = _detection_path(gallery_id, image_id)
    if not p.exists():
        return None
    with p.open() as fh:
        return json.load(fh)


def _write_detection(data: dict[str, Any]) -> None:
    gallery_id = data["gallery_id"]
    image_id = data["image_id"]
    p = _detection_path(gallery_id, image_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as fh:
        json.dump(data, fh, indent=2)


# ---------------------------------------------------------------------------
# Per-image detection
# ---------------------------------------------------------------------------


def _process_image(
    image_path: str,
    gallery_id: str,
    image_id: str,
    analyzer,
    face_cfg: dict,
    base_mtimes: list[float],
    write_crops: bool = False,
) -> tuple[dict[str, Any], bool]:
    """Detect faces in one image, write detection JSON + embeddings.

    Returns (detection_record, was_skipped).
    """
    det_path = _detection_path(gallery_id, image_id)
    image_mtime = os.path.getmtime(image_path)

    if _detection_is_fresh(det_path, image_mtime, base_mtimes):
        with det_path.open() as fh:
            return json.load(fh), True

    min_size = face_cfg.get("min_face_size_px", FACE_DEFAULT_MIN_FACE_SIZE_PX)
    min_conf = face_cfg.get("min_detection_confidence", FACE_DEFAULT_MIN_DETECTION_CONFIDENCE)

    arr, full_w, full_h = _load_oriented_rgb(image_path)
    small, scale = _resize_for_detection(arr, _DETECT_MAX_DIM)

    detections = analyze_image(analyzer, small)

    image_stem = Path(image_path).stem
    faces = []
    for det in detections:
        x1, y1, x2, y2 = det.bbox_px
        # Scale back to full image coordinates
        fx1, fy1, fx2, fy2 = x1 / scale, y1 / scale, x2 / scale, y2 / scale

        # Filter: minimum face size
        face_w = fx2 - fx1
        face_h = fy2 - fy1
        if min(face_w, face_h) < min_size:
            continue
        # Filter: minimum confidence
        if det.detection_confidence < min_conf:
            continue

        face_id = _face_id(gallery_id, image_id, det.face_index)
        bbox_norm = _bbox_normalised(fx1, fy1, fx2, fy2, full_w, full_h)

        # Persist embedding
        emb_path = _embedding_path(face_id)
        save_embedding(emb_path, det.embedding)

        # Optionally write crop JPEG
        if write_crops:
            _write_crop(arr, fx1, fy1, fx2, fy2, gallery_id, image_stem, det.face_index)

        faces.append(
            {
                "face_id": face_id,
                "face_index": det.face_index,
                "bbox": bbox_norm,
                "detection_confidence": round(det.detection_confidence, 6),
                "identity_id": None,
                "provenance": FACE_PROVENANCE_UNASSIGNED,
                "match_score": None,
            }
        )

    record = {
        "gallery_id": gallery_id,
        "image_id": image_id,
        "source_filename": os.path.basename(image_path),
        "faces": faces,
    }
    _write_detection(record)
    return record, False


# ---------------------------------------------------------------------------
# Crop writing (for faces show)
# ---------------------------------------------------------------------------


def _write_crop(
    arr: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    gallery_id: str,
    image_stem: str,
    face_index: int,
) -> None:
    """Write a crop JPEG for a detected face."""
    h, w = arr.shape[:2]
    x1c = max(0, int(x1))
    y1c = max(0, int(y1))
    x2c = min(w, int(x2))
    y2c = min(h, int(y2))
    if x2c <= x1c or y2c <= y1c:
        return
    crop_arr = arr[y1c:y2c, x1c:x2c]
    crop_img = Image.fromarray(crop_arr, "RGB")
    out_path = _crop_path(gallery_id, image_stem, face_index)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    crop_img.save(str(out_path), "JPEG", quality=_CROP_JPEG_QUALITY)


def write_crops_for_image(image_path: str, gallery_id: str, image_id: str) -> list[str]:
    """Write crop JPEGs for all detected faces in an image.  Returns list of written paths."""
    det = _load_detection(gallery_id, image_id)
    if det is None or not det["faces"]:
        return []
    arr, full_w, full_h = _load_oriented_rgb(image_path)
    image_stem = Path(image_path).stem
    written = []
    for face in det["faces"]:
        bx, by, bw, bh = face["bbox"]
        x1 = bx * full_w
        y1 = by * full_h
        x2 = (bx + bw) * full_w
        y2 = (by + bh) * full_h
        out = _crop_path(gallery_id, image_stem, face["face_index"])
        _write_crop(arr, x1, y1, x2, y2, gallery_id, image_stem, face["face_index"])
        written.append(str(out))
    return written


# ---------------------------------------------------------------------------
# Label application
# ---------------------------------------------------------------------------


def _resolve_face_ref(
    ref: FaceRef,
    all_detections: dict[str, dict[str, Any]],
    detection_key: str,
) -> tuple[str, int] | None:
    """Resolve a FaceRef to (detection_key, face_index) or None if invalid.

    Returns a warning string instead of None when the image exists but ref is bad.
    """
    key = detection_key  # "{gallery_id}:{image_id}"
    det = all_detections.get(key)
    if det is None:
        return None

    faces = det["faces"]
    if not faces:
        return None

    if ref.face is not None:
        # Explicit face index
        for face in faces:
            if face["face_index"] == ref.face:
                return key, ref.face
        return None

    # face=None: only valid when exactly one face in the image
    if len(faces) == 1:
        return key, faces[0]["face_index"]

    return None  # ambiguous — apply_labels will warn


def apply_labels(
    all_detections: dict[str, dict[str, Any]],
    store: IdentityStore,
    warnings_out: list[str],
) -> None:
    """Apply positive and negative labels from the identity store to detection records.

    Mutates face dicts inside all_detections in place.
    Appends warning strings to warnings_out for unresolvable refs.
    """
    # Build fast lookup: (gallery_id, image_filename) → detection_key
    # Detection keys are "{gallery_id}:{image_id}"
    filename_to_key: dict[tuple[str, str], str] = {
        (det["gallery_id"], det["source_filename"]): f"{det['gallery_id']}:{det['image_id']}"
        for det in all_detections.values()
    }

    def _det_key_for_ref(ref: FaceRef) -> str | None:
        return filename_to_key.get((ref.gallery, ref.image))

    for slug, entry in store.identities.items():
        # Apply positives
        for ref in entry.positives:
            det_key = _det_key_for_ref(ref)
            if det_key is None:
                warnings_out.append(
                    f"Positive for '{slug}': image {ref.gallery}/{ref.image} not found — skipping."
                )
                continue
            det = all_detections[det_key]
            faces = det["faces"]
            if not faces:
                warnings_out.append(
                    f"Positive for '{slug}': {ref.gallery}/{ref.image} has no detected faces."
                )
                continue
            if ref.face is not None:
                matched = [f for f in faces if f["face_index"] == ref.face]
                if not matched:
                    warnings_out.append(
                        f"Positive for '{slug}': face index {ref.face} not found in "
                        f"{ref.gallery}/{ref.image} — skipping."
                    )
                    continue
                target_faces = matched
            elif len(faces) == 1:
                target_faces = faces
            else:
                warnings_out.append(
                    f"Positive for '{slug}': {ref.gallery}/{ref.image} has {len(faces)} faces "
                    f"but no face index specified — skipping.  Use 'faces assign --face N'."
                )
                continue
            for face in target_faces:
                face["identity_id"] = slug
                face["provenance"] = FACE_PROVENANCE_POSITIVE
                face["match_score"] = 1.0

        # Apply negatives (build block set — provenance stays, marks block only)
        for ref in entry.negatives:
            det_key = _det_key_for_ref(ref)
            if det_key is None:
                continue  # image deleted; silently skip negatives
            det = all_detections[det_key]
            for face in det["faces"]:
                if ref.face is not None and face["face_index"] != ref.face:
                    continue
                if face["provenance"] != FACE_PROVENANCE_POSITIVE:
                    face["_blocked_identities"] = face.get("_blocked_identities", set()) | {slug}
                    face["provenance"] = FACE_PROVENANCE_NEGATIVE_BLOCKED


# ---------------------------------------------------------------------------
# Auto-tag sync
# ---------------------------------------------------------------------------


def _sync_auto_tags(
    all_detections: dict[str, dict[str, Any]],
    auto_tag_prefix: str,
) -> None:
    """Rewrite person:* auto-tags in image sidecar YAMLs.

    For each image: collect distinct named identity slugs (positive or propagated),
    remove existing <prefix>* tags, add <prefix><slug> for each named identity,
    preserve all other tags.  Anonymous id_unnamed_* slugs are NOT auto-tagged.
    """
    source = config["source_path"]

    for det in all_detections.values():
        gallery_id = det["gallery_id"]
        source_filename = det["source_filename"]
        image_path = os.path.join(source, gallery_id, source_filename)
        sidecar_path = os.path.splitext(image_path)[0] + ".yaml"

        named_slugs: set[str] = set()
        for face in det["faces"]:
            prov = face.get("provenance")
            if prov in (FACE_PROVENANCE_POSITIVE, "propagated"):
                slug = face.get("identity_id")
                if slug and not slug.startswith("id_unnamed_"):
                    named_slugs.add(slug)

        # Load existing sidecar or start fresh
        if os.path.exists(sidecar_path):
            with open(sidecar_path) as fh:
                sidecar = yaml.safe_load(fh) or {}
        else:
            sidecar = {}

        existing_tags: list[str] = sidecar.get("tags") or []
        if not isinstance(existing_tags, list):
            existing_tags = [existing_tags]

        # Remove old auto-tags; keep manual tags
        filtered = [t for t in existing_tags if not str(t).startswith(auto_tag_prefix)]
        new_tags = filtered + sorted(f"{auto_tag_prefix}{slug}" for slug in named_slugs)

        if new_tags == existing_tags:
            continue  # nothing changed; skip write

        sidecar["tags"] = new_tags
        with open(sidecar_path, "w") as fh:
            yaml.dump(sidecar, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _write_index_json(
    images_processed: int,
    images_skipped: int,
    faces_detected: int,
    identities_named: int,
    face_cfg: dict,
) -> None:
    data = {
        "schema_version": FACE_SCHEMA_VERSION,
        "model_bundle_version": FACE_MODEL_BUNDLE_VERSION,
        "last_run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "images_processed": images_processed,
        "images_skipped": images_skipped,
        "faces_detected": faces_detected,
        "identities_named": identities_named,
        "thresholds": {
            "match_threshold": face_cfg.get("match_threshold", FACE_DEFAULT_MATCH_THRESHOLD),
            "cluster_threshold": face_cfg.get("cluster_threshold", FACE_DEFAULT_CLUSTER_THRESHOLD),
            "min_face_size_px": face_cfg.get("min_face_size_px", FACE_DEFAULT_MIN_FACE_SIZE_PX),
            "min_detection_confidence": face_cfg.get(
                "min_detection_confidence", FACE_DEFAULT_MIN_DETECTION_CONFIDENCE
            ),
        },
    }
    out = _gallery_metadata_dir() / FACES_INDEX_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        json.dump(data, fh, indent=2)


def _write_centroids(centroids: dict[str, np.ndarray]) -> None:
    emb_dir = _gallery_metadata_dir() / FACES_EMBEDDINGS_DIR
    emb_dir.mkdir(parents=True, exist_ok=True)
    for slug, centroid in centroids.items():
        p = emb_dir / f"_centroid_{slug}.bin"
        p.write_bytes(centroid.astype(np.float32).tobytes())


def _write_clusters_json(all_detections: dict[str, dict[str, Any]]) -> None:
    clusters: dict[str, list[str]] = {}
    for det in all_detections.values():
        for face in det["faces"]:
            if face["provenance"] == "cluster":
                cluster_id = face["identity_id"]
                clusters.setdefault(cluster_id, []).append(face["face_id"])

    out = _gallery_metadata_dir() / FACES_CLUSTERS_LATEST_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        json.dump(clusters, fh, indent=2)


# ---------------------------------------------------------------------------
# Export merge (Option B: faces[] on export/metadata image JSON)
# ---------------------------------------------------------------------------


def detection_to_export_faces(det: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build export-safe face assignment list from a detection record."""
    if det is None:
        return []
    export_faces: list[dict[str, Any]] = []
    for face in det.get("faces", []):
        export_faces.append(
            {
                "face_index": face["face_index"],
                "face_id": face["face_id"],
                "identity_id": face.get("identity_id"),
                "provenance": face.get("provenance"),
                "bbox": face["bbox"],
            }
        )
    return export_faces


def _detection_image_paths(
    all_detections: dict[str, dict[str, Any]],
) -> list[tuple[str, str, str]]:
    """Build (gallery_id, image_id, path) tuples from detection records."""
    return [
        (det["gallery_id"], det["image_id"], "")
        for det in all_detections.values()
    ]


def export_faces_to_image_metadata(
    all_image_paths: list[tuple[str, str, str]],
    all_detections: dict[str, dict[str, Any]],
) -> None:
    """Patch export/metadata/{gallery}/{image_id}.json with faces[] assignments."""
    for gallery_id, image_id, _ in all_image_paths:
        export_path = _export_image_metadata_path(gallery_id, image_id)
        if not export_path.exists():
            continue
        det_key = f"{gallery_id}:{image_id}"
        faces = detection_to_export_faces(all_detections.get(det_key))
        with export_path.open() as fh:
            image_meta = json.load(fh)
        image_meta[EXPORT_IMAGE_FACES_FIELD] = faces
        with export_path.open("w") as fh:
            json.dump(image_meta, fh, indent=2)


# ---------------------------------------------------------------------------
# Embedding loader (used by face_matching)
# ---------------------------------------------------------------------------


def _embedding_loader(ref: FaceRef) -> np.ndarray | None:
    """Load embedding for a FaceRef by constructing the face_id.

    Called from build_exemplar_map via face_matching.
    Note: This requires that all_detections are already loaded so we can look up
    the image_id from (gallery, source_filename).

    This version is a closure created in run() to capture the detection index.
    """
    # Stub — real loader is built in run() as a closure
    return None


# ---------------------------------------------------------------------------
# Main stage entry point
# ---------------------------------------------------------------------------


def run() -> FaceStageResult:
    """Run the face pipeline stage.

    Returns:
        FaceStageResult with counts and elapsed time.
    """
    t0 = time.time()
    _migrate_legacy_face_metadata()
    face_cfg: dict = config.get("faces", {})
    match_threshold = face_cfg.get("match_threshold", FACE_DEFAULT_MATCH_THRESHOLD)
    cluster_threshold = face_cfg.get("cluster_threshold", FACE_DEFAULT_CLUSTER_THRESHOLD)
    min_cluster_size = face_cfg.get(
        "hdbscan_min_cluster_size", FACE_DEFAULT_HDBSCAN_MIN_CLUSTER_SIZE
    )
    auto_tag_prefix = face_cfg.get("auto_tag_prefix", FACE_DEFAULT_AUTO_TAG_PREFIX)

    source = config["source_path"]
    base_mtimes = _source_mtimes()
    errors: list[tuple[str, str]] = []
    stage_warnings: list[str] = []

    # ── Phase 1: detect + embed ────────────────────────────────────────────
    gallery_names = sorted(
        g
        for g in os.listdir(source)
        if is_source_gallery_dirname(g) and os.path.isdir(os.path.join(source, g))
    )
    all_image_paths: list[tuple[str, str, str]] = []  # (gallery_id, image_id, abs_path)
    for gallery_id in gallery_names:
        gallery_path = os.path.join(source, gallery_id)
        for filename in sorted(os.listdir(gallery_path)):
            if not filename.lower().endswith(SUPPORTED_FORMATS):
                continue
            image_id = hashlib.md5(f"{gallery_id}:{filename}".encode()).hexdigest()[:12]
            all_image_paths.append((gallery_id, image_id, os.path.join(gallery_path, filename)))

    analyzer = get_face_analyzer()

    images_processed = 0
    images_skipped = 0
    total_images = len(all_image_paths)

    with create_file_progress(console) as progress:
        overall_task = progress.add_task("", total=total_images)

        for gallery_id, image_id, image_path in all_image_paths:
            filename = os.path.basename(image_path)
            set_file_task_description(
                progress,
                overall_task,
                PROGRESS_STAGE_FACE_DETECTION,
                gallery_id,
                filename,
            )
            try:
                _record, was_skipped = _process_image(
                    image_path=image_path,
                    gallery_id=gallery_id,
                    image_id=image_id,
                    analyzer=analyzer,
                    face_cfg=face_cfg,
                    base_mtimes=base_mtimes,
                    write_crops=False,
                )
                if was_skipped:
                    images_skipped += 1
                else:
                    images_processed += 1
            except Exception as exc:
                errors.append((image_path, str(exc)))
            progress.advance(overall_task)

        set_phase_task_description(progress, overall_task, PROGRESS_STAGE_FACE_MATCHING)

        # ── Phase 2: load all detections ──────────────────────────────────
        all_detections: dict[str, dict] = {}
        faces_detected = 0
        for gallery_id, image_id, _ in all_image_paths:
            det = _load_detection(gallery_id, image_id)
            if det is None:
                continue
            key = f"{gallery_id}:{image_id}"
            all_detections[key] = det
            faces_detected += len(det["faces"])

        # ── Phase 3: load embeddings ────────────────────────────────────────
        embeddings: dict[str, np.ndarray] = {}
        for det in all_detections.values():
            for face in det["faces"]:
                fid = face["face_id"]
                ep = _embedding_path(fid)
                if ep.exists():
                    try:
                        embeddings[fid] = load_embedding(ep)
                    except Exception:
                        pass

        # ── Phase 4: load identities + apply labels ─────────────────────────
        store: IdentityStore = load_identities(Path("."))
        apply_labels(all_detections, store, stage_warnings)

        # ── Phase 5: build exemplar map + propagate ─────────────────────────
        # Build filename→detection_key lookup for the embedding loader
        filename_to_det_key: dict[tuple[str, str], str] = {
            (det["gallery_id"], det["source_filename"]): key
            for key, det in all_detections.items()
        }

        def _ref_embedding_loader(ref: FaceRef) -> np.ndarray | None:
            det_key = filename_to_det_key.get((ref.gallery, ref.image))
            if det_key is None:
                return None
            det = all_detections[det_key]
            face_index = ref.face
            for face in det["faces"]:
                if face["provenance"] == FACE_PROVENANCE_POSITIVE:
                    if face_index is None or face["face_index"] == face_index:
                        fid = face["face_id"]
                        return embeddings.get(fid)
            return None

        # Build flat faces list for propagation + clustering
        all_faces = [face for det in all_detections.values() for face in det["faces"]]
        # Attach gallery_id + source_filename to each face for propagation lookups
        for det in all_detections.values():
            for face in det["faces"]:
                face["gallery_id"] = det["gallery_id"]
                face["source_filename"] = det["source_filename"]

        exemplar_map = build_exemplar_map(store, _ref_embedding_loader)
        neg_map = build_negative_map(store)

        propagate_identities(
            faces=all_faces,
            exemplar_map=exemplar_map,
            neg_map=neg_map,
            embeddings=embeddings,
            match_threshold=match_threshold,
        )

        set_phase_task_description(progress, overall_task, PROGRESS_STAGE_FACE_CLUSTERING)

        # ── Phase 6: cluster unassigned ─────────────────────────────────────
        cluster_run_id = hashlib.md5(
            ":".join(sorted(embeddings.keys())).encode()
        ).hexdigest()[:16]

        cluster_unassigned(
            faces=all_faces,
            embeddings=embeddings,
            cluster_threshold=cluster_threshold,
            min_cluster_size=min_cluster_size,
            cluster_run_id=cluster_run_id,
        )

        set_phase_task_description(progress, overall_task, PROGRESS_STAGE_FACE_FINALIZING)

        # ── Phase 7: compute centroids ────────────────────────────────────
        centroids = compute_centroids(exemplar_map)
        _write_centroids(centroids)

        # ── Phase 8: write output files ─────────────────────────────────────
        # Write back updated detection records (with identity_id, provenance, match_score)
        for det in all_detections.values():
            # Strip internal working keys before writing
            for face in det["faces"]:
                face.pop("_blocked_identities", None)
                face.pop("gallery_id", None)
                face.pop("source_filename", None)
            _write_detection(det)

        identities_named = len([s for s in store.identities if not s.startswith("id_unnamed_")])
        clusters_anonymous = len(
            {f["identity_id"] for f in all_faces if f.get("provenance") == "cluster"}
        )

        _write_index_json(images_processed, images_skipped, faces_detected, identities_named, face_cfg)
        _write_clusters_json(all_detections)

        # ── Phase 9: export faces[] to image metadata ───────────────────────
        export_faces_to_image_metadata(all_image_paths, all_detections)

        # ── Phase 10: sync auto-tags ────────────────────────────────────────
        _sync_auto_tags(all_detections, auto_tag_prefix)

    return FaceStageResult(
        images_processed=images_processed,
        images_skipped=images_skipped,
        faces_detected=faces_detected,
        identities_named=identities_named,
        clusters_anonymous=clusters_anonymous,
        elapsed=time.time() - t0,
        errors=errors,
        warnings=stage_warnings,
    )


# ---------------------------------------------------------------------------
# Standalone recluster (no re-detection)
# ---------------------------------------------------------------------------


def recluster() -> int:
    """Drop all cluster assignments and rerun clustering on unassigned faces only.

    Returns the number of faces placed into clusters.
    """
    face_cfg: dict = config.get("faces", {})
    cluster_threshold = face_cfg.get("cluster_threshold", FACE_DEFAULT_CLUSTER_THRESHOLD)
    min_cluster_size = face_cfg.get(
        "hdbscan_min_cluster_size", FACE_DEFAULT_HDBSCAN_MIN_CLUSTER_SIZE
    )

    source = config["source_path"]
    gallery_names = sorted(
        g
        for g in os.listdir(source)
        if is_source_gallery_dirname(g) and os.path.isdir(os.path.join(source, g))
    )

    all_detections: dict[str, dict] = {}
    for gallery_id in gallery_names:
        det_dir = _gallery_metadata_dir() / FACES_DETECTIONS_DIR / gallery_id
        if not det_dir.exists():
            continue
        for det_file in sorted(det_dir.glob("*.json")):
            with det_file.open() as fh:
                det = json.load(fh)
            key = f"{det['gallery_id']}:{det['image_id']}"
            all_detections[key] = det

    embeddings: dict[str, np.ndarray] = {}
    all_faces = []
    for det in all_detections.values():
        for face in det["faces"]:
            face["gallery_id"] = det["gallery_id"]
            face["source_filename"] = det["source_filename"]
            all_faces.append(face)
            fid = face["face_id"]
            ep = _embedding_path(fid)
            if ep.exists():
                try:
                    embeddings[fid] = load_embedding(ep)
                except Exception:
                    pass

    # Reset existing cluster assignments
    for face in all_faces:
        if face.get("provenance") == "cluster":
            face["identity_id"] = None
            face["provenance"] = FACE_PROVENANCE_UNASSIGNED

    cluster_run_id = hashlib.md5(
        ":".join(sorted(embeddings.keys())).encode()
    ).hexdigest()[:16]

    placed = cluster_unassigned(
        faces=all_faces,
        embeddings=embeddings,
        cluster_threshold=cluster_threshold,
        min_cluster_size=min_cluster_size,
        cluster_run_id=cluster_run_id,
    )

    # Write back
    for det in all_detections.values():
        for face in det["faces"]:
            face.pop("gallery_id", None)
            face.pop("source_filename", None)
        _write_detection(det)

    _write_clusters_json(all_detections)
    export_faces_to_image_metadata(_detection_image_paths(all_detections), all_detections)
    return placed


# ---------------------------------------------------------------------------
# Standalone propagate (with optional dry-run)
# ---------------------------------------------------------------------------


def propagate(dry_run: bool = False, identity_filter: str | None = None) -> list[dict]:
    """Run propagation without full update.  Returns list of change records."""
    face_cfg: dict = config.get("faces", {})
    match_threshold = face_cfg.get("match_threshold", FACE_DEFAULT_MATCH_THRESHOLD)

    source = config["source_path"]
    gallery_names = sorted(
        g
        for g in os.listdir(source)
        if is_source_gallery_dirname(g) and os.path.isdir(os.path.join(source, g))
    )

    all_detections: dict[str, dict] = {}
    for gallery_id in gallery_names:
        det_dir = _gallery_metadata_dir() / FACES_DETECTIONS_DIR / gallery_id
        if not det_dir.exists():
            continue
        for det_file in sorted(det_dir.glob("*.json")):
            with det_file.open() as fh:
                det = json.load(fh)
            key = f"{det['gallery_id']}:{det['image_id']}"
            all_detections[key] = det

    embeddings: dict[str, np.ndarray] = {}
    all_faces = []
    for det in all_detections.values():
        for face in det["faces"]:
            face["gallery_id"] = det["gallery_id"]
            face["source_filename"] = det["source_filename"]
            all_faces.append(face)
            fid = face["face_id"]
            ep = _embedding_path(fid)
            if ep.exists():
                try:
                    embeddings[fid] = load_embedding(ep)
                except Exception:
                    pass

    store = load_identities(Path("."))
    filename_to_det_key = {
        (det["gallery_id"], det["source_filename"]): key
        for key, det in all_detections.items()
    }

    def _loader(ref: FaceRef) -> np.ndarray | None:
        dk = filename_to_det_key.get((ref.gallery, ref.image))
        if dk is None:
            return None
        det = all_detections[dk]
        for face in det["faces"]:
            if face["provenance"] == FACE_PROVENANCE_POSITIVE:
                if ref.face is None or face["face_index"] == ref.face:
                    return embeddings.get(face["face_id"])
        return None

    exemplar_map = build_exemplar_map(store, _loader)
    if identity_filter:
        exemplar_map = {k: v for k, v in exemplar_map.items() if k == identity_filter}
    neg_map = build_negative_map(store)

    # Snapshot before
    before = {f["face_id"]: (f.get("identity_id"), f.get("provenance")) for f in all_faces}

    propagate_identities(
        faces=all_faces,
        exemplar_map=exemplar_map,
        neg_map=neg_map,
        embeddings=embeddings,
        match_threshold=match_threshold,
    )

    changes = []
    for face in all_faces:
        fid = face["face_id"]
        old_id, old_prov = before[fid]
        new_id = face.get("identity_id")
        new_prov = face.get("provenance")
        if old_id != new_id or old_prov != new_prov:
            changes.append(
                {
                    "face_id": fid,
                    "gallery": face["gallery_id"],
                    "filename": face["source_filename"],
                    "face_index": face["face_index"],
                    "old_identity": old_id,
                    "new_identity": new_id,
                    "old_provenance": old_prov,
                    "new_provenance": new_prov,
                    "match_score": face.get("match_score"),
                }
            )

    if not dry_run:
        for det in all_detections.values():
            for face in det["faces"]:
                face.pop("gallery_id", None)
                face.pop("source_filename", None)
            _write_detection(det)
        export_faces_to_image_metadata(_detection_image_paths(all_detections), all_detections)

    # Restore working keys for dry-run output
    return changes
