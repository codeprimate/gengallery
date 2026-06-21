"""Unit tests for face_matching: propagation, clustering, centroids, and priority rules."""

from __future__ import annotations

import numpy as np

from gengallery.constants import (
    FACE_PROVENANCE_CLUSTER,
    FACE_PROVENANCE_POSITIVE,
    FACE_PROVENANCE_PROPAGATED,
    FACE_PROVENANCE_UNASSIGNED,
)
from gengallery.services.face_labeling import (
    FaceRef,
    IdentityEntry,
    IdentityStore,
)
from gengallery.services.face_matching import (
    build_exemplar_map,
    cluster_unassigned,
    compute_centroids,
    propagate_identities,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_vec(dim: int = 512) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float32)
    v[0] = 1.0
    return v


def _vec(index: int, dim: int = 512) -> np.ndarray:
    """Unit vector in a given dimension (all dimensions orthogonal to each other)."""
    v = np.zeros(dim, dtype=np.float32)
    v[index % dim] = 1.0
    return v


def _near_vec(base: np.ndarray, noise: float = 0.01) -> np.ndarray:
    """A vector very close to base (high cosine similarity)."""
    v = base + np.random.default_rng(42).normal(0, noise, size=base.shape).astype(np.float32)
    return v / np.linalg.norm(v)


def _face(face_id: str, gallery: str = "gal", filename: str = "img.jpg",
          face_index: int = 0, provenance: str = FACE_PROVENANCE_UNASSIGNED,
          identity_id: str | None = None) -> dict:
    return {
        "face_id": face_id,
        "face_index": face_index,
        "gallery_id": gallery,
        "source_filename": filename,
        "provenance": provenance,
        "identity_id": identity_id,
        "match_score": None,
    }


# ---------------------------------------------------------------------------
# build_exemplar_map
# ---------------------------------------------------------------------------


def test_build_exemplar_map_returns_loaded_embeddings() -> None:
    store = IdentityStore()
    store.identities["alice"] = IdentityEntry(
        display_name="Alice",
        positives=[FaceRef(gallery="gal", image="img.jpg", face=0)],
    )
    emb = _vec(0)
    embeddings = {("gal", "img.jpg"): emb}

    def loader(ref: FaceRef) -> np.ndarray | None:
        return embeddings.get((ref.gallery, ref.image))

    result = build_exemplar_map(store, loader)
    assert "alice" in result
    assert len(result["alice"]) == 1


def test_build_exemplar_map_skips_missing_embedding() -> None:
    store = IdentityStore()
    store.identities["alice"] = IdentityEntry(
        display_name="Alice",
        positives=[FaceRef(gallery="gal", image="missing.jpg")],
    )

    def loader(ref: FaceRef) -> np.ndarray | None:
        return None

    result = build_exemplar_map(store, loader)
    assert "alice" not in result  # no exemplars loaded → excluded


# ---------------------------------------------------------------------------
# propagate_identities
# ---------------------------------------------------------------------------


def test_propagation_assigns_above_threshold() -> None:
    alice_emb = _vec(0)
    face_emb = _near_vec(alice_emb, noise=0.05)
    exemplar_map = {"alice": [alice_emb]}
    neg_map: dict = {}
    embeddings = {"f1": face_emb}

    faces = [_face("f1")]
    propagate_identities(faces, exemplar_map, neg_map, embeddings, match_threshold=0.5)

    assert faces[0]["identity_id"] == "alice"
    assert faces[0]["provenance"] == FACE_PROVENANCE_PROPAGATED


def test_propagation_skips_below_threshold() -> None:
    alice_emb = _vec(0)
    orthogonal_emb = _vec(1)  # cosine sim = 0
    exemplar_map = {"alice": [alice_emb]}
    neg_map: dict = {}
    embeddings = {"f1": orthogonal_emb}

    faces = [_face("f1")]
    propagate_identities(faces, exemplar_map, neg_map, embeddings, match_threshold=0.5)

    assert faces[0]["identity_id"] is None
    assert faces[0]["provenance"] == FACE_PROVENANCE_UNASSIGNED


def test_propagation_respects_negative_blocks() -> None:
    alice_emb = _vec(0)
    face_emb = _near_vec(alice_emb, noise=0.01)
    exemplar_map = {"alice": [alice_emb]}
    neg_map = {("gal", "img.jpg", 0): {"alice"}}
    embeddings = {"f1": face_emb}

    faces = [_face("f1", gallery="gal", filename="img.jpg", face_index=0)]
    propagate_identities(faces, exemplar_map, neg_map, embeddings, match_threshold=0.5)

    assert faces[0]["identity_id"] is None


def test_propagation_does_not_override_positive() -> None:
    alice_emb = _vec(0)
    exemplar_map = {"bob": [alice_emb]}  # Bob's exemplar looks like alice
    neg_map: dict = {}
    embeddings = {"f1": alice_emb}

    faces = [_face("f1", provenance=FACE_PROVENANCE_POSITIVE, identity_id="alice")]
    propagate_identities(faces, exemplar_map, neg_map, embeddings, match_threshold=0.0)

    # Must not change positive assignment
    assert faces[0]["identity_id"] == "alice"
    assert faces[0]["provenance"] == FACE_PROVENANCE_POSITIVE


def test_propagation_picks_best_scoring_identity() -> None:
    emb_a = _vec(0)
    emb_b = _vec(1)
    # Face is close to alice, far from bob
    face_emb = _near_vec(emb_a, noise=0.01)
    exemplar_map = {"alice": [emb_a], "bob": [emb_b]}
    neg_map: dict = {}
    embeddings = {"f1": face_emb}

    faces = [_face("f1")]
    propagate_identities(faces, exemplar_map, neg_map, embeddings, match_threshold=0.5)

    assert faces[0]["identity_id"] == "alice"


# ---------------------------------------------------------------------------
# cluster_unassigned
# ---------------------------------------------------------------------------


def test_clustering_groups_similar_faces() -> None:
    base = _vec(0)
    embeddings = {
        "f1": _near_vec(base, noise=0.01),
        "f2": _near_vec(base, noise=0.01),
        "f3": _vec(1),  # very different
    }
    faces = [_face("f1"), _face("f2"), _face("f3")]

    placed = cluster_unassigned(
        faces, embeddings, cluster_threshold=0.3, min_cluster_size=2
    )

    cluster_ids = {f["identity_id"] for f in faces if f["provenance"] == FACE_PROVENANCE_CLUSTER}
    assert placed == 2
    assert len(cluster_ids) == 1  # f1 and f2 share a cluster
    assert all(cid.startswith("id_unnamed_") for cid in cluster_ids)


def test_clustering_below_min_size_stays_unassigned() -> None:
    """A single-face cluster should not be assigned (min_cluster_size=2)."""
    base = _vec(0)
    embeddings = {"f1": base}
    faces = [_face("f1")]

    placed = cluster_unassigned(faces, embeddings, cluster_threshold=0.3, min_cluster_size=2)
    assert placed == 0
    assert faces[0]["provenance"] == FACE_PROVENANCE_UNASSIGNED


def test_clustering_skips_positive_faces() -> None:
    base = _vec(0)
    embs = {
        "f1": _near_vec(base, 0.01),
        "f2": _near_vec(base, 0.01),
    }
    faces = [
        _face("f1", provenance=FACE_PROVENANCE_POSITIVE, identity_id="alice"),
        _face("f2"),
    ]

    cluster_unassigned(faces, embs, cluster_threshold=0.3, min_cluster_size=1)

    assert faces[0]["provenance"] == FACE_PROVENANCE_POSITIVE
    assert faces[0]["identity_id"] == "alice"


# ---------------------------------------------------------------------------
# compute_centroids
# ---------------------------------------------------------------------------


def test_compute_centroids_l2_normalised() -> None:
    emb1 = _vec(0)
    emb2 = _vec(0)  # same direction → centroid = same direction
    centroids = compute_centroids({"alice": [emb1, emb2]})
    c = centroids["alice"]
    assert abs(np.linalg.norm(c) - 1.0) < 1e-5


def test_compute_centroids_empty_exemplars_excluded() -> None:
    centroids = compute_centroids({"alice": []})
    assert "alice" not in centroids


# ---------------------------------------------------------------------------
# Assignment priority
# ---------------------------------------------------------------------------


def test_priority_positive_beats_propagation() -> None:
    """A face already marked positive must not be overwritten by propagation."""
    alice_emb = _vec(0)
    exemplar_map = {"bob": [alice_emb]}  # bob's exemplar is identical to alice's
    embeddings = {"fx": alice_emb}
    faces = [
        {
            "face_id": "fx",
            "face_index": 0,
            "gallery_id": "gal",
            "source_filename": "img.jpg",
            "provenance": FACE_PROVENANCE_POSITIVE,
            "identity_id": "alice",
            "match_score": 1.0,
        }
    ]
    propagate_identities(faces, exemplar_map, {}, embeddings, match_threshold=0.0)
    assert faces[0]["identity_id"] == "alice"
    assert faces[0]["provenance"] == FACE_PROVENANCE_POSITIVE
