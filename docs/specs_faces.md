# Feature: Face Detection, Identity Clustering, and CLI Labeling

## Problem Statement

GenGallery processes personal photo libraries into a static site. People in photos are identified only through manual per-image YAML tags. That does not scale for large archives and offers no cross-gallery “photos of this person” capability.

The operator (single user, self-hosted) needs a **build-time face pipeline** that:

1. Detects faces and computes embeddings for every gallery image.
2. Groups unlabeled faces by visual resemblance into anonymous identity clusters.
3. Accepts **definite positive labels** via CLI (image path + optional face index).
4. Propagates named identities across the library using exemplar similarity.
5. Keeps all rich face metadata **outside `public_html`** (including for encrypted galleries).

Recognition quality improves through **labeled exemplars** (prototype learning), not through fine-tuning the neural network.

## Context & Constraints

| Constraint | Decision |
|---|---|
| Audience | Single operator; no multi-user auth or labeling UI in v1 |
| Models | **Required** core dependency (not optional extra) |
| Model delivery | Download on first use → `$XDG_CACHE_HOME/gengallery/models/` (shared; default `~/.cache/gengallery/models/`) |
| Deploy | `gengallery push ssh` syncs `public_html` only; face metadata stays local |
| Encrypted galleries | Detection on **source** plaintext; face metadata never in `public_html` |
| v1 UI | CLI only — no person browse pages, no review HTML site |
| Pipeline | New stage after Images: **Images → Faces → Videos → Gallery Index → Site** (5 stages) |

## Goals

- Detect faces and store embeddings for all supported image formats.
- Let the operator assign identities by source image path (`faces assign`).
- Auto-propagate identity assignments on every `gengallery update`.
- Re-evaluate propagated assignments each update; positives and negatives are immutable unless changed via CLI.
- Maintain anonymous `id_unnamed_*` clusters for discovery.
- Sync `person:{slug}` tags into image sidecar YAML automatically.
- Provide `faces show` with crop JPEGs for multi-face disambiguation.

## Non-Goals (v1)

- Video face detection (keyframes or clips).
- Bulk assign by gallery (`--gallery`, `--solo-only`).
- Person browse pages or face overlays in generated HTML.
- Face data inside encrypted metadata blobs under `public_html`.
- Optional model install / feature flag to disable faces.
- Fine-tuning embedding models on user labels.
- Deploying `export/metadata/faces/` via SSH.

## Requirements

### Functional Requirements

#### Pipeline stage (`face_processor`)

On each `gengallery update`, after image processing and before video processing:

1. **Discover** images the same way `image_processor.discover_galleries()` does (supported formats in `galleries/{id}/`).
2. **Detect** faces per image (bounding box + confidence).
3. **Embed** each face (L2-normalized vector).
4. **Persist** detections, embeddings, crops, clusters, and assignments under `export/metadata/faces/`.
5. **Apply labels** from `galleries/identities.yaml` (positives and negatives).
6. **Propagate** named identities to unlabeled faces above `match_threshold`.
7. **Cluster** remaining unlabeled, non-noise faces into anonymous `id_unnamed_*` groups.
8. **Write auto-tags** to image sidecar YAML files (`person:{slug}`).
9. **Skip** unchanged images when source mtime and label mtime allow (see Incremental processing).

Per-image failures are recorded and do not abort the stage (same pattern as `image_processor`).

#### Identity model

- **Face**: one detected face in one image (`face_id`, bbox, embedding, detection confidence).
- **Identity**: a named or anonymous person cluster (`identity_id` slug).
- **Positive**: operator assertion that a specific face belongs to an identity (authoritative).
- **Negative**: operator assertion that a specific face does **not** belong to an identity (blocks propagation to that identity for that face).
- **Propagated**: assignment inferred by similarity to positive exemplars (recomputed each update).
- **Cluster**: anonymous identity group (`id_unnamed_{hex}`) for unlabeled faces.

**Assignment priority** (highest wins; lower layers never override higher):

1. Positive label for `(gallery, image, face_index)`
2. Negative label (prevents assignment to that identity only)
3. Propagated match (best identity by exemplar similarity)
4. Anonymous cluster membership (unlabeled only)

#### Matching strategy

For each identity with at least one positive exemplar:

- **Propagation score** = `max(cosine_similarity(face, exemplar_i))` over all positive exemplar embeddings.
- Assign to the identity with the highest score if `score >= match_threshold` and no negative blocks it.
- **Centroid** (mean of positive exemplars, re-normalized) is used for **cluster hints** and `recluster` alignment only — not as the primary propagation matcher.

#### Source of truth: `galleries/identities.yaml`

Version-controlled at `galleries/identities.yaml` (sibling to gallery folders, not inside a gallery directory).

```yaml
identities:
  alice:
    display_name: Alice
    positives:
      - gallery: "20240715"
        image: portrait.jpg
      - gallery: "20240715"
        image: party.jpg
        face: 0
    negatives: []   # optional; same shape as positives
```

- **Slug** (`alice`): stable key used in CLI, metadata, and `person:alice` tags.
- **`display_name`**: human-readable; defaults to title-case slug on auto-create.
- **`positives` / `negatives`**: list of `{gallery, image, face?}` records.
- Omitting `face` when the image has exactly one detection is allowed.
- Omitting `face` when multiple detections exist is an error at apply time (matches CLI assign rules).

CLI mutates this file for `assign`, `unassign`, `reject`, and `merge`.

#### CLI commands

All commands accept optional `PROJECT` path (default: cwd), consistent with existing CLI.

| Command | Purpose |
|---|---|
| `gengallery faces assign <slug> <path>… [--face N]` | Add positive(s); auto-create identity if missing |
| `gengallery faces unassign <path>… [--face N]` | Remove positive(s); clear propagated assignment for that face |
| `gengallery faces reject <slug> <path>… [--face N]` | Add negative(s) |
| `gengallery faces show <path>…` | Print detections; write crop JPEGs |
| `gengallery faces merge <source_slug> <target_slug>` | Merge identities (positives, negatives, exemplars) |
| `gengallery faces recluster` | Full recluster of unlabeled faces only |
| `gengallery faces propagate [--dry-run] [--identity <slug>]` | Run propagation without full update (tuning aid) |

**Path resolution** (first match wins):

1. `{source_path}/{gallery}/{filename}` when `path` is `gallery/file.jpg`
2. `galleries/{gallery}/{filename}` relative to project root
3. Absolute path under project root
4. Otherwise: `CliUserError` with clear message

**`faces assign` multi-face rule**: if an image has more than one face and `--face N` is omitted → error with message to run `faces show`.

**`faces show` output**:

- Terminal: gallery, image, `face_index`, normalized bbox, confidence, `identity_id`, `provenance`.
- Crops: `export/metadata/faces/crops/{gallery_id}/{image_stem}_{face_index}.jpg`

**Slug validation**: `^[a-z][a-z0-9-]*$` (lowercase, hyphens; no spaces).

#### Auto-tags (`person:{slug}`)

After assignments settle each update:

- For each image, collect distinct identity slugs present on any face (positive or propagated).
- Rewrite **system-managed** tags in the image sidecar YAML (`{image}.yaml`):
  - Remove existing tags matching `person:*`.
  - Add `person:{slug}` for each identity on that image.
  - Preserve all other tags (manual tags untouched).
- If no sidecar exists, create one with `tags: [person:…]` only.
- Named identities only — anonymous `id_unnamed_*` slugs are **not** auto-tagged.

Tag prefix is configurable (`faces.auto_tag_prefix`, default `person:`).

#### Encrypted galleries

- Face detection reads **source** files from `galleries/{id}/` (plaintext).
- No face fields are added to `public_html` encrypted metadata blobs.
- No face fields in stripped per-image JSON that mirrors public encrypted metadata.
- All face artifacts live under `export/metadata/faces/` only.

### Technical Constraints

#### Models

- **Detector**: RetinaFace (or equivalent ONNX face detector).
- **Embedder**: ArcFace 512-d (or equivalent ONNX recognizer).
- **Runtime**: `onnxruntime` (CPU default; GPU optional later without spec change).
- **Cache**: `$XDG_CACHE_HOME/gengallery/models/` (default `~/.cache/gengallery/models/`); shared across projects; created on first use.
- **Version pin**: record `model_bundle_version` in `export/metadata/faces/index.json`; changing models may require full re-embed (documented operator action).

Add to `pyproject.toml` dependencies (required, not optional):

- `onnxruntime`
- `numpy`
- Supporting stack for model load and image tensor prep (e.g. `opencv-python-headless` or equivalent — choose at implementation time; must support EXIF-oriented crops).

#### Configuration (`config.yaml`)

```yaml
faces:
  match_threshold: 0.55          # propagation assignment minimum cosine similarity
  cluster_threshold: 0.45        # agglomerative merge threshold for recluster
  min_face_size_px: 40           # ignore smaller detections (shorter bbox side)
  min_detection_confidence: 0.90
  auto_tag_prefix: "person:"
  hdbscan_min_cluster_size: 2    # anonymous clusters need ≥2 faces; else outlier
```

All keys have documented defaults if omitted.

#### Performance

- Target: personal archives (low thousands of images) on CPU without timeout.
- Incremental skip when face outputs are newer than max(source image mtime, `identities.yaml` mtime, `config.yaml` faces section mtime).
- Detection may use thumbnail-scale image (e.g. longest side 1024) for speed; store bbox in normalized coordinates relative to **oriented** full image.

#### Security & privacy

- Operator controls all data locally.
- `export/metadata/faces/` contains biometric embeddings — never deployed by default.
- Face embeddings under `export/metadata/faces/` remain project-local and gitignored via `export*/`.

### Edge Cases & Error Handling

| Scenario | Behavior |
|---|---|
| No faces in image | `assign` / `reject` → error; `show` → “0 faces” |
| Image not found | `CliUserError` |
| Gallery not found | `CliUserError` |
| `face` index out of range | `CliUserError` |
| Positive and negative same face+identity | Error on write; reject after assign for same pair is no-op or error (pick one: **error**) |
| Merge source == target | `CliUserError` |
| Merge with conflicting positives on same face | Target wins; source positive removed |
| Source image deleted but positive remains in YAML | Warn during apply; skip record; do not crash |
| Model download fails | Stage fails with actionable message (network, disk) |
| Two identities, high similarity (twins) | Negatives and higher `match_threshold` per identity (future); v1: operator uses `reject` |
| Model version change | `faces/index.json` records version; mismatch flags `reembed_required` in index |
| `identities.yaml` missing | Treat as empty identities; file created on first `assign` |
| Image skipped by image_processor | Face stage still runs if source exists (faces are independent outputs) |
| Propagated reassignment | Allowed each update — provenance changes from `propagated` to unassigned or another identity |
| Positive reassignment | Only via `unassign` then `assign` — never overridden by propagation |

## Data Layout

```
.
├── galleries/
│   ├── identities.yaml                  # source of truth: names, positives, negatives
│   └── YYYYMMDD/
│       ├── gallery.yaml
│       ├── photo.jpg
│       └── photo.yaml                   # receives auto person:* tags
└── export/
    └── metadata/
        ├── galleries.json               # unchanged: no face fields in v1
        ├── YYYYMMDD/
        │   └── {image_id}.json          # unchanged: no face fields in v1
        └── faces/
            ├── index.json               # schema version, model version, thresholds snapshot, stats
            ├── identities.json          # derived: slugs, display_names, centroids, exemplar refs
            ├── clusters/
            │   └── latest.json          # anonymous cluster membership
            ├── detections/
            │   └── {gallery_id}/
            │       └── {image_id}.json  # per-image face list (no raw embedding)
            ├── embeddings/
            │   └── {face_id}.bin        # float32 vector, L2-normalized
            └── crops/
                └── {gallery_id}/
                    └── {image_stem}_{face_index}.jpg
```

### `export/metadata/faces/index.json`

```json
{
  "schema_version": 1,
  "model_bundle_version": "insightface-buffalo-l-v1",
  "last_run_at": "2026-06-18T12:00:00Z",
  "images_processed": 1200,
  "images_skipped": 11800,
  "faces_detected": 3400,
  "identities_named": 12,
  "thresholds": {
    "match_threshold": 0.55,
    "cluster_threshold": 0.45,
    "min_face_size_px": 40,
    "min_detection_confidence": 0.9
  }
}
```

### Per-detection record (`detections/{gallery}/{image_id}.json`)

```json
{
  "gallery_id": "20240715",
  "image_id": "a1b2c3d4e5f6",
  "source_filename": "party.jpg",
  "faces": [
    {
      "face_id": "f8e2…",
      "face_index": 0,
      "bbox": [0.12, 0.08, 0.22, 0.28],
      "detection_confidence": 0.98,
      "identity_id": "alice",
      "provenance": "positive",
      "match_score": 1.0
    }
  ]
}
```

- `bbox`: `[x, y, width, height]` normalized 0–1 relative to oriented image.
- `face_index`: stable ordering by `(y, x)` of bbox top-left (deterministic across runs on same detector version).
- `face_id`: `sha256("{gallery_id}:{image_id}:{face_index}:{model_bundle_version}")[:16]`.
- `provenance`: `positive` | `negative_blocked` | `propagated` | `cluster` | `unassigned`.
- `match_score`: similarity that produced assignment (1.0 for positive).

Embeddings are **not** duplicated in this file; keyed by `face_id` in `embeddings/`.

### Derived `identities.json`

```json
{
  "alice": {
    "display_name": "Alice",
    "exemplar_face_ids": ["f8e2…", "a1b3…"],
    "centroid_face_id": "internal-cache",
    "positive_count": 5,
    "propagated_count": 142
  }
}
```

Centroid vector stored as `embeddings/_centroid_{slug}.bin` or inline in identities.json (implementation choice; prefer separate bin file).

## Technical Approach

### Implementation strategy

1. Add `src/gengallery/services/face_processor.py` mirroring `image_processor` / `video_processor` patterns: `discover_*`, `run()`, Rich progress, `FaceStageResult`.
2. Add `src/gengallery/services/face_labeling.py` for YAML I/O, path resolution, assign/unassign/reject/merge logic.
3. Add `src/gengallery/services/face_matching.py` for exemplar similarity, propagation, clustering.
4. Add `src/gengallery/services/face_models.py` for download, cache, ONNX session lifecycle.
5. Add `src/gengallery/commands/faces.py` and register `faces` subcommand tree in `cli.py`.
6. Update `update.py`: `_STAGE_TOTAL = 5`, insert face stage between images and videos.
7. Add `FaceStageResult` to `pipeline_types.py`.
8. Add constants: `CMD_FACES`, `.gengallery` dirname, metadata paths, tag prefix.
9. On gallery/image cleanup in `gallery_processor`, extend to remove orphaned face artifacts (detections, embeddings, crops for deleted `image_id`).

Follow existing conventions: shared `config` dict via `apply_runtime_config`, `CliUserError` for user mistakes, `rich` for output.

### Face stage internal algorithm

```
for each image (incremental):
    load oriented image
    detect faces → filter by min_size, min_confidence
  for each face:
    compute embedding
    write embedding bin + update detection record (unassigned)

load galleries/identities.yaml
for each positive:
    resolve face → set identity, provenance=positive, match_score=1.0
for each negative:
    mark face as blocked for that identity

propagate:
  for each face where provenance is unassigned or propagated (not positive):
    score against all named identities (exemplar max-sim)
    assign best if score >= match_threshold and not negative-blocked
    else provenance=unassigned

cluster (unassigned faces only):
  agglomerative or HDBSCAN with cluster_threshold
  assign id_unnamed_{sha256(cluster_run_id + cluster_index)[:8]}

update centroids for named identities
write clusters/latest.json
sync person:* tags to sidecar YAMLs
write faces/index.json
```

`faces recluster` drops anonymous cluster assignments and reruns the cluster step only (never touches positives/negatives/propagated named assignments).

`faces propagate --dry-run` prints would-assign / would-change without writing (except dry-run report to stdout).

### Affected components

| File / area | Change |
|---|---|
| `src/gengallery/cli.py` | Register `faces` subcommand |
| `src/gengallery/commands/faces.py` | New CLI handlers |
| `src/gengallery/constants.py` | `CMD_FACES`, path constants |
| `src/gengallery/services/face_*.py` | New modules |
| `src/gengallery/services/update.py` | 5-stage pipeline |
| `src/gengallery/services/pipeline_types.py` | `FaceStageResult` |
| `src/gengallery/services/gallery_processor.py` | Cleanup orphaned face artifacts |
| `pyproject.toml` | Required deps |
| `.gitignore` / init scaffold | `.gengallery/` |
| `docs/specs.md` | Cross-link (implementation task) |
| `tests/python/test_face_*.py` | New tests |
| `tests/python/test_update_orchestrator.py` | Expect 5 stages |

**Not changed in v1**: `generator.py` templates, `deploy_ssh.py`, encrypted blob schema, `galleries.json` shape.

### Dependencies & integration

- **image_processor**: shares `SUPPORTED_FORMATS`, `config`, `apply_runtime_config`; auto-tags write sidecar YAML using same path convention as `get_image_metadata()`.
- **gallery_processor**: cleanup hook only; does not aggregate face data into `galleries.json` in v1.
- **generator**: consumes auto `person:*` tags if present in aggregated metadata (existing tag pipeline) — no face-specific template work.
- **video_processor**: unchanged; runs after faces.

### Testing strategy

| Area | Approach |
|---|---|
| Path resolution | Unit tests with tmp_path gallery trees |
| YAML round-trip | assign/unassign/merge on temp `identities.yaml` |
| Matching / propagation | Fixed synthetic embeddings (vectors with known cosine sims) |
| Priority rules | positive > negative > propagated > cluster |
| Auto-tags | Assert sidecar YAML rewritten correctly |
| Pipeline order | `test_update_orchestrator` expects `image → faces → video → gallery → generator` |
| ONNX inference | Integration test marked `@pytest.mark.integration` with bundled tiny fixture or mocked session |
| CI default | Unit tests only; integration optional |

Use `ruff` / `pytest` per project norms.

## Acceptance Criteria

- [ ] `gengallery update` runs a Faces stage (stage 2 of 5) without error on example gallery.
- [ ] First run downloads models into `$XDG_CACHE_HOME/gengallery/models/` (shared across projects).
- [ ] `gengallery faces assign alice 20240715/portrait.jpg` creates `galleries/identities.yaml` entry and, after update, sets face provenance to `positive`.
- [ ] Multi-face image without `--face` fails with actionable error.
- [ ] `gengallery faces show` writes crops under `export/metadata/faces/crops/`.
- [ ] Propagation runs automatically on update and re-evaluates prior propagated assignments.
- [ ] Positives are never changed by propagation or recluster.
- [ ] `gengallery faces reject` prevents propagation to named identity for that face.
- [ ] `gengallery faces merge a b` combines identities; `a` slug removed.
- [ ] `gengallery faces recluster` affects only unlabeled faces.
- [ ] Anonymous clusters use `id_unnamed_*` slugs in derived metadata.
- [ ] Auto `person:{slug}` tags appear in image sidecar YAML; manual non-`person:` tags preserved.
- [ ] No files under `export/metadata/faces/` are written to `public_html`.
- [ ] Encrypted gallery images produce face metadata under `export/metadata/faces/` only.
- [ ] Deleting a source image removes corresponding face artifacts on next update/index pass.
- [ ] `tests/python` passes; `ruff` clean on new modules.

## Implementation Tasks

- [ ] Add `docs/specs_faces.md` (this document) and link from `docs/README.md`
- [ ] Add dependencies; model cache uses XDG cache dir (not per-project)
- [ ] Implement `face_models.py` (download, cache, inference)
- [ ] Implement `face_processor.py` (detect, embed, incremental skip)
- [ ] Implement `face_matching.py` (propagate, cluster, centroid)
- [ ] Implement `face_labeling.py` (YAML + path resolution)
- [ ] Implement `commands/faces.py` + CLI registration
- [ ] Wire stage into `update.py` + `FaceStageResult`
- [ ] Implement auto-tag sync to sidecar YAML
- [ ] Extend `gallery_processor` cleanup for face artifacts
- [ ] Unit tests + update orchestrator test
- [ ] Integration test (optional marker) for ONNX path

## Risk Assessment

### Potential issues

| Risk | Impact |
|---|---|
| Auto-tag writes mutate source YAML | Git noise; merge conflicts with manual edits |
| `galleries*/*/**` gitignore vs `identities.yaml` | `identities.yaml` is at `galleries/` root — **not** ignored; document clearly |
| Model download size / CI | Large first fetch; CI should mock inference |
| Propagation false positives | Wrong `person:*` tags; mitigated by thresholds and `reject` |
| Child/adult same slug | Single identity may need many positives; exemplar max-sim helps |
| Detector version change | `face_index` / `face_id` stability; require reembed |
| Performance on 10k+ images | CPU time; incremental skip essential |
| `generator` tag pages expose `person:*` | Intended side effect of auto-tags on public galleries |

### Mitigation strategies

- Document that `person:*` tags are system-managed.
- `faces propagate --dry-run` before lowering threshold.
- Pin `model_bundle_version`; migration command later if needed (`faces reembed`).
- Record provenance on every assignment for audit via `faces show`.

### Investigation requirements

- Confirm ONNX bundle choice and license (InsightFace buffalo_l or equivalent).
- Validate detection on HEIC/HEIF with same orientation handling as `image_processor`.
- Benchmark CPU time per image on representative library.
- Decide OpenCV vs pure Pillow for crop/tensor prep.

## Deep Dive: Second-Order Effects

### 1. Auto-tags and the existing tag system

`person:alice` tags flow into `gallery_processor` → `galleries.json` → `generator` tag listing pages. **Public galleries** will gain browseable person tag pages without face-specific UI. That is a side effect of v1 auto-tagging, not face metadata leakage (no embeddings in HTML).

For **encrypted** galleries, existing rules still apply: YAML tags do not populate tag listing pages. Auto `person:*` tags on encrypted images are stored in source sidecar YAML locally but do not create public tag pages.

### 2. Mutating source sidecar YAML

Auto-tags rewrite files under `galleries/`, which are gitignored (`galleries*/*/**`). Operator backups must include `galleries/` and `galleries/identities.yaml`. `identities.yaml` is **not** gitignored by default — positives should be committed if desired.

### 3. Separation from `galleries.json`

Face data intentionally avoids `galleries.json` in v1 so `generator` and deploy never see embeddings. Future person pages must read `export/metadata/faces/` at build time (local-only builds) or a new explicit export step.

### 4. Encrypted metadata architecture

Current encrypted inner metadata lives in `public_html` blobs. Face data deliberately breaks that pattern — richer operator-only metadata in `export/metadata/faces/`. Long term, other encrypted fields might migrate similarly; out of scope for v1.

### 5. Interaction with image skip logic

`image_processor` may skip unchanged images while `identities.yaml` changed. Face stage must compare mtime against `identities.yaml` and re-run apply/propagate/cluster even when detection is skipped.

### 6. Identity slug collisions with gallery IDs

Slugs like `20240715` are valid but confusing. Document recommendation: use name slugs (`alice`), not gallery IDs.

### 7. `merge` and propagation

After merge, re-run propagation for affected faces. Target identity exemplar set grows; some propagated faces under source slug need reassignment to target.

### 8. Negative labels vs multi-identity competition

A face blocked for `alice` can still propagate to `bob`. Negatives are per (face, identity) pair, not global.

### 9. Cluster identity lifecycle

`id_unnamed_*` groups may merge when recluster runs. Faces in clusters are not auto-tagged. Assigning one face in a cluster does not auto-label siblings (operator may assign multiple paths or rely on propagation).

### 10. Operator workflow dependency

Recognition quality scales with positive count and angle diversity. Spec assumes operator will run `assign` on several clear photos per person before expecting propagation to fill the library.

## Future Work (post-v1)

- Video keyframe face detection.
- `faces assign --gallery {id} --solo-only` bulk helper.
- Person browse pages generated from `export/metadata/faces/`.
- Local review HTML report.
- `faces identity rename` CLI.
- Optional metadata deploy path.
- GPU execution provider for ONNX.
- `faces reembed` after model upgrade.

## Glossary

| Term | Meaning |
|---|---|
| Exemplar | Embedding from a positively labeled face |
| Propagation | Automatic assignment by similarity to exemplars |
| Provenance | How an assignment was made |
| Anonymous identity | Cluster with `id_unnamed_*` slug, not named in YAML |
| Positive | CLI-confirmed face → identity mapping in `identities.yaml` |

## Document History

- **2026-06-18**: Initial specification from stakeholder Q&A (two confirmation rounds).
