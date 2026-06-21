"""Face matching: propagation, clustering, and centroid computation.

This module operates on already-detected embeddings and the identity store.
It has no I/O responsibilities — callers load embeddings and write outputs.

Assignment priority (highest wins; lower layers never override higher):
  1. Positive label (provenance = "positive")
  2. Negative label (provenance = "negative_blocked")
  3. Propagated match (provenance = "propagated")
  4. Anonymous cluster (provenance = "cluster")
  5. No assignment (provenance = "unassigned")

Public API
----------
build_exemplar_map(store, embedding_loader)
    Build {slug: [embeddings]} from the identity store's positive labels.

propagate_identities(faces, exemplar_map, negative_map, match_threshold)
    Assign identities to unassigned/propagated faces by exemplar similarity.

cluster_unassigned(faces, embeddings_map, cluster_threshold, min_cluster_size)
    Group remaining unassigned faces into anonymous id_unnamed_* clusters.

compute_centroids(exemplar_map)
    Return {slug: centroid_embedding} (mean, re-normalised).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

import numpy as np

from gengallery.constants import (
    FACE_DEFAULT_CLUSTER_THRESHOLD,
    FACE_DEFAULT_HDBSCAN_MIN_CLUSTER_SIZE,
    FACE_DEFAULT_MATCH_THRESHOLD,
    FACE_PROVENANCE_CLUSTER,
    FACE_PROVENANCE_PROPAGATED,
    FACE_PROVENANCE_UNASSIGNED,
)
from gengallery.services.face_labeling import IdentityStore
from gengallery.services.face_models import cosine_similarity

# ---------------------------------------------------------------------------
# Exemplar map
# ---------------------------------------------------------------------------

EmbeddingLoader = Callable[[str], np.ndarray | None]


def build_exemplar_map(
    store: IdentityStore,
    embedding_loader: EmbeddingLoader,
) -> dict[str, list[np.ndarray]]:
    """Build {slug: [embedding, ...]} from an identity store's positives.

    ``embedding_loader`` receives a face_id string and returns the float32 numpy
    embedding array, or None if the face has no stored embedding (e.g. image deleted).

    Args:
        store: Loaded IdentityStore.
        embedding_loader: Callable(face_id) → ndarray | None.

    Returns:
        Dict mapping identity slug to list of L2-normalised exemplar embeddings.
        Identities with zero successfully loaded exemplars are excluded.
    """
    exemplars: dict[str, list[np.ndarray]] = {}
    for slug, entry in store.identities.items():
        loaded: list[np.ndarray] = []
        for ref in entry.positives:
            emb = embedding_loader(ref)
            if emb is not None:
                loaded.append(emb)
        if loaded:
            exemplars[slug] = loaded
    return exemplars


def build_negative_map(store: IdentityStore) -> dict[tuple, set[str]]:
    """Build {(gallery, image, face): {slug, ...}} from all negative labels.

    Used during propagation to block assignment of a face to blocked identities.
    """
    neg_map: dict[tuple, set[str]] = {}
    for slug, entry in store.identities.items():
        for ref in entry.negatives:
            key = (ref.gallery, ref.image, ref.face)
            neg_map.setdefault(key, set()).add(slug)
            # face=None means "any face in this image" — handled separately in _is_blocked
    return neg_map


def _is_blocked(
    neg_map: dict[tuple, set[str]],
    gallery: str,
    image: str,
    face_index: int,
    slug: str,
) -> bool:
    """Return True if negative labels block assigning slug to this face."""
    # Exact face match
    if slug in neg_map.get((gallery, image, face_index), set()):
        return True
    # face=None means "any face in this image"
    if slug in neg_map.get((gallery, image, None), set()):
        return True
    return False


# ---------------------------------------------------------------------------
# Propagation
# ---------------------------------------------------------------------------


def propagate_identities(
    faces: list[dict[str, Any]],
    exemplar_map: dict[str, list[np.ndarray]],
    neg_map: dict[tuple, set[str]],
    embeddings: dict[str, np.ndarray],
    match_threshold: float = FACE_DEFAULT_MATCH_THRESHOLD,
) -> int:
    """Assign identities to eligible faces by exemplar max-cosine-similarity.

    Mutates face dicts in place.  Only faces with provenance ``unassigned`` or
    ``propagated`` are eligible — ``positive`` and ``negative_blocked`` are skipped.

    Args:
        faces: List of face record dicts (each must have face_id, gallery_id,
               image_id / source_filename, face_index, provenance, identity_id).
        exemplar_map: {slug: [embedding, ...]} from build_exemplar_map().
        neg_map: Negative label index from build_negative_map().
        embeddings: {face_id: ndarray} for all loaded face embeddings.
        match_threshold: Minimum cosine similarity to propagate.

    Returns:
        Number of faces that received a new propagated identity.
    """
    if not exemplar_map:
        return 0

    assigned_count = 0
    for face in faces:
        if face["provenance"] == "positive":
            continue

        face_id = face["face_id"]
        emb = embeddings.get(face_id)
        if emb is None:
            continue

        gallery = face["gallery_id"]
        image = face["source_filename"]
        fidx = face["face_index"]

        best_slug: str | None = None
        best_score = match_threshold - 1e-9  # must strictly exceed threshold

        for slug, exemplar_embeddings in exemplar_map.items():
            if _is_blocked(neg_map, gallery, image, fidx, slug):
                continue
            # Propagation score = max cosine similarity across all exemplars
            score = max(cosine_similarity(emb, ex) for ex in exemplar_embeddings)
            if score > best_score:
                best_score = score
                best_slug = slug

        old_provenance = face["provenance"]
        if best_slug is not None:
            face["identity_id"] = best_slug
            face["provenance"] = FACE_PROVENANCE_PROPAGATED
            face["match_score"] = round(best_score, 6)
            if old_provenance != FACE_PROVENANCE_PROPAGATED:
                assigned_count += 1
        else:
            face["identity_id"] = None
            face["provenance"] = FACE_PROVENANCE_UNASSIGNED
            face["match_score"] = None

    return assigned_count


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def _stable_cluster_id(cluster_run_id: str, cluster_index: int) -> str:
    """Produce a stable id_unnamed_* slug from run ID + cluster index."""
    raw = f"{cluster_run_id}:{cluster_index}"
    hexdigest = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"id_unnamed_{hexdigest}"


def cluster_unassigned(
    faces: list[dict[str, Any]],
    embeddings: dict[str, np.ndarray],
    cluster_threshold: float = FACE_DEFAULT_CLUSTER_THRESHOLD,
    min_cluster_size: int = FACE_DEFAULT_HDBSCAN_MIN_CLUSTER_SIZE,
    cluster_run_id: str = "default",
) -> int:
    """Group unassigned faces into anonymous id_unnamed_* clusters.

    Uses agglomerative clustering (average linkage, cosine distance).
    Only faces with provenance ``unassigned`` are clustered.
    Mutates face dicts in place.

    Args:
        faces: Face record dicts (see propagate_identities for shape).
        embeddings: {face_id: ndarray} for all loaded face embeddings.
        cluster_threshold: Distance threshold for agglomerative clustering.
        min_cluster_size: Minimum cluster size to assign a cluster ID (else unassigned).
        cluster_run_id: Seed for stable cluster ID generation.

    Returns:
        Number of faces placed into a named anonymous cluster.
    """
    from sklearn.cluster import AgglomerativeClustering  # type: ignore[import-untyped]

    eligible = [
        f for f in faces
        if f["provenance"] == FACE_PROVENANCE_UNASSIGNED and f["face_id"] in embeddings
    ]

    if len(eligible) < 2:
        return 0

    matrix = np.stack([embeddings[f["face_id"]] for f in eligible])

    # Cosine distance = 1 - cosine_similarity.  L2-normalised vectors: dist = 1 - dot.
    # AgglomerativeClustering accepts precomputed distance matrix.
    dot_products = matrix @ matrix.T
    # Clip to [0, 2] to handle floating-point noise around perfect matches
    dist_matrix = np.clip(1.0 - dot_products, 0.0, 2.0)

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=cluster_threshold,
        metric="precomputed",
        linkage="average",
    )
    labels = clustering.fit_predict(dist_matrix)

    # Count cluster sizes; only keep clusters meeting min_cluster_size
    from collections import Counter

    label_counts = Counter(labels.tolist())
    valid_labels = {lbl for lbl, cnt in label_counts.items() if cnt >= min_cluster_size}

    placed = 0
    for face, label in zip(eligible, labels.tolist()):
        if label in valid_labels:
            cluster_id = _stable_cluster_id(cluster_run_id, label)
            face["identity_id"] = cluster_id
            face["provenance"] = FACE_PROVENANCE_CLUSTER
            face["match_score"] = None
            placed += 1

    return placed


# ---------------------------------------------------------------------------
# Centroids
# ---------------------------------------------------------------------------


def compute_centroids(
    exemplar_map: dict[str, list[np.ndarray]],
) -> dict[str, np.ndarray]:
    """Compute per-identity centroid embeddings (mean of exemplars, re-normalised).

    Args:
        exemplar_map: {slug: [embedding, ...]} from build_exemplar_map().

    Returns:
        {slug: centroid_embedding} — each centroid is L2-normalised float32.
        Identities with no exemplars are excluded.
    """
    centroids: dict[str, np.ndarray] = {}
    for slug, embs in exemplar_map.items():
        if not embs:
            continue
        mean = np.mean(np.stack(embs), axis=0)
        norm = np.linalg.norm(mean)
        if norm > 1e-9:
            mean = mean / norm
        centroids[slug] = mean.astype(np.float32)
    return centroids
