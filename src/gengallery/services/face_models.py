"""Face model management: download, cache, and inference session for the face pipeline.

Wraps InsightFace's FaceAnalysis (buffalo_l) via onnxruntime.  Downloaded ONNX
weights are stored once under the XDG cache directory (shared across all gallery
projects on the same machine):

    $XDG_CACHE_HOME/gengallery/models/   (default: ~/.cache/gengallery/models/)

Public API
----------
face_model_cache_root()
    Resolve the InsightFace ``root`` directory (parent of ``models/``).

get_face_analyzer()
    Return a ready FaceAnalysis instance. Downloads models on first use.

analyze_image(analyzer, oriented_rgb_array)
    Run detection + embedding on an already-oriented RGB numpy array.
    Returns a list of FaceDetection named tuples.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from gengallery.constants import (
    ENV_XDG_CACHE_HOME,
    FACE_MODEL_BUNDLE,
    FACE_MODEL_BUNDLE_VERSION,
    FACE_MODELS_SUBDIR,
    XDG_CACHE_APP_DIRNAME,
)

# Detection size fed to the ONNX detector model.
# Larger → better small-face recall; smaller → faster.
_DET_SIZE = (640, 640)


@contextlib.contextmanager
def _suppress_third_party_console_output():
    """Silence InsightFace/onnxruntime init prints (they use bare ``print``)."""
    with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(
        devnull
    ):
        yield


@dataclass
class FaceDetection:
    """Single detected face with embedding and metadata."""

    face_index: int
    bbox_px: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels
    detection_confidence: float
    embedding: np.ndarray  # float32, L2-normalised, shape (512,)


def xdg_cache_home() -> Path:
    """Return the XDG cache home directory.

    Uses ``$XDG_CACHE_HOME`` when set; otherwise ``~/.cache`` (XDG default).
    """
    override = os.environ.get(ENV_XDG_CACHE_HOME)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache"


def face_model_cache_root() -> Path:
    """Return the InsightFace root directory for gengallery model weights.

    InsightFace stores bundles under ``<root>/models/<bundle_name>/``.
    For gengallery this resolves to::

        $XDG_CACHE_HOME/gengallery/models/<bundle>/
    """
    return xdg_cache_home() / XDG_CACHE_APP_DIRNAME


def get_face_analyzer():  # type: ignore[return]
    """Return a ready InsightFace FaceAnalysis instance.

    Downloads buffalo_l models to the shared XDG cache on first use.

    Returns:
        insightface.app.FaceAnalysis configured for CPU inference.

    Raises:
        RuntimeError: If model download or ONNX session initialisation fails.
    """
    try:
        from insightface.app import FaceAnalysis  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "insightface is required for the face pipeline. "
            "Install it: pip install insightface"
        ) from exc

    cache_root = face_model_cache_root()
    models_dir = cache_root / FACE_MODELS_SUBDIR
    models_dir.mkdir(parents=True, exist_ok=True)

    try:
        with _suppress_third_party_console_output():
            app = FaceAnalysis(
                name=FACE_MODEL_BUNDLE,
                root=str(cache_root),
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=0, det_size=_DET_SIZE)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to initialise face model '{FACE_MODEL_BUNDLE}': {exc}\n"
            "Check network access and disk space. Models are downloaded to "
            f"{models_dir}."
        ) from exc

    return app


def model_bundle_version() -> str:
    """Return the pinned model bundle version string recorded in index.json."""
    return FACE_MODEL_BUNDLE_VERSION


def analyze_image(analyzer, oriented_rgb: np.ndarray) -> list[FaceDetection]:
    """Run face detection and embedding on an oriented RGB image.

    Args:
        analyzer: insightface FaceAnalysis instance from get_face_analyzer().
        oriented_rgb: HxWx3 uint8 numpy array in RGB order (already EXIF-rotated).

    Returns:
        List of FaceDetection sorted by (top_y, left_x) for deterministic face_index.
        Empty list if no faces are detected.
    """
    # InsightFace expects BGR
    bgr = oriented_rgb[:, :, ::-1]
    faces = analyzer.get(bgr)

    if not faces:
        return []

    detections: list[FaceDetection] = []
    for face in faces:
        bbox = face.bbox  # [x1, y1, x2, y2] float32
        score = float(face.det_score)
        emb = face.normed_embedding  # shape (512,), already L2-normalised

        detections.append(
            FaceDetection(
                face_index=-1,  # assigned after sort
                bbox_px=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                detection_confidence=score,
                embedding=emb.astype(np.float32),
            )
        )

    # Deterministic ordering: sort by (top-left y, then x)
    detections.sort(key=lambda d: (d.bbox_px[1], d.bbox_px[0]))
    for idx, det in enumerate(detections):
        det.face_index = idx

    return detections


def load_embedding(path: str | Path) -> np.ndarray:
    """Load a float32 L2-normalised embedding vector from a .bin file."""
    data = np.frombuffer(Path(path).read_bytes(), dtype=np.float32)
    return data


def save_embedding(path: str | Path, embedding: np.ndarray) -> None:
    """Persist a float32 embedding vector to a .bin file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(embedding.astype(np.float32).tobytes())


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalised vectors (equals their dot product)."""
    return float(np.dot(a, b))
