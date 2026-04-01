#!/usr/bin/env python
"""
Transcode gallery videos from galleries/<id>/ (root) to thumbnail + H.264 in export .../video/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.text import Text

from crypto_v1 import derive_metadata_key_bytes, derive_storage_token_bytes
from envelope_v1 import encrypt_payload
from image_processor import (
    METADATA_BLOB_EXTENSION,
    METADATA_VARIANT_DIR,
    config,
    derive_encryption_params,
    encrypt_file,
    get_image_metadata,
    get_variant_extension,
)
from video_encoding import (
    VIDEO_MAX_DURATION_SECONDS,
    build_aac_audio_args,
    build_libx264_codec_args,
    build_scale_vf,
    clamp_duration_seconds,
    compute_output_dimensions,
    mtime_exif_datetime,
    normalize_creation_time_tag,
    poster_seek_seconds,
    select_video_bitrate_bps,
)

console = Console()

SUPPORTED_VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v")
VIDEO_ID_NAMESPACE_PREFIX = "video:"
TEMP_VIDEO_PLAINTEXT_SUFFIX = ".tmp.mp4"
TEMP_THUMB_PLAINTEXT_SUFFIX = ".tmp.thumb.jpg"
GCM_NONCE_MATERIAL_PREFIX_VIDEO_THUMBNAIL = "pge-v1/gcm-nonce|video-thumbnail"
GCM_NONCE_MATERIAL_PREFIX_VIDEO_PLAYBACK = "pge-v1/gcm-nonce|video-playback"
GCM_NONCE_MATERIAL_PREFIX_METADATA_BLOB = "pge-v1/gcm-nonce|metadata-blob"
INNER_VIDEO_METADATA_SCHEMA_VERSION = 2
FFMPEG_THUMB_QSCALE = 3


def generate_video_id(basename: str, gallery_id: str, is_encrypted: bool) -> str:
    unique_string = f"{gallery_id}:{VIDEO_ID_NAMESPACE_PREFIX}{basename}"
    if is_encrypted:
        return hashlib.sha256(unique_string.encode()).hexdigest()[:16]
    return hashlib.md5(unique_string.encode()).hexdigest()[:12]


def ffprobe_video(path: str) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-show_entries",
        "format=duration,tags",
        "-of",
        "json",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def parse_ffprobe_dimensions_and_duration(data: dict) -> tuple[int, int, float, str | None]:
    streams = data.get("streams") or []
    if not streams:
        raise ValueError("No video stream found")
    w = int(streams[0].get("width") or 0)
    h = int(streams[0].get("height") or 0)
    if w < 1 or h < 1:
        raise ValueError("Invalid video dimensions")
    fmt = data.get("format") or {}
    duration = float(fmt.get("duration") or 0.0)
    tags = fmt.get("tags") or {}
    creation = tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate")
    return w, h, duration, creation


def create_inner_video_metadata_dict(output_metadata: dict) -> dict:
    return {
        "inner_schema_version": INNER_VIDEO_METADATA_SCHEMA_VERSION,
        "media_type": "video",
        "video_id": output_metadata["id"],
        "filename": output_metadata["filename"],
        "title": output_metadata.get("title", ""),
        "caption": output_metadata.get("caption", ""),
        "exif": output_metadata.get("exif", {}),
        "tags": output_metadata.get("tags", []),
    }


def write_encrypted_video_metadata_blob(output_metadata: dict, gallery_id: str, password: str) -> None:
    storage_token_bytes = derive_storage_token_bytes(password, gallery_id)
    metadata_key = derive_metadata_key_bytes(storage_token_bytes, gallery_id)
    inner_bytes = json.dumps(
        create_inner_video_metadata_dict(output_metadata),
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    nonce_material = (
        f"{GCM_NONCE_MATERIAL_PREFIX_METADATA_BLOB}|{gallery_id}|{output_metadata['id']}"
    ).encode("utf-8")
    encrypted_blob = encrypt_payload(inner_bytes, metadata_key, nonce_material=nonce_material)
    metadata_output_dir = os.path.join(
        config["output_path"],
        "public_html",
        "galleries",
        gallery_id,
        METADATA_VARIANT_DIR,
    )
    os.makedirs(metadata_output_dir, exist_ok=True)
    blob_path = os.path.join(
        metadata_output_dir,
        f"{output_metadata['id']}{METADATA_BLOB_EXTENSION}",
    )
    with open(blob_path, "wb") as f:
        f.write(encrypted_blob)


def create_public_video_metadata_dict(full: dict) -> dict:
    return {
        "id": full["id"],
        "filename": full["filename"],
        "url": full["url"],
        "media_type": "video",
        "thumbnail_path": full["thumbnail_path"],
        "playback_path": full["playback_path"],
        "metadata_path": full.get("metadata_path", ""),
    }


def create_video_metadata_dict(
    basename: str,
    video_id: str,
    gallery_id: str,
    exif_datetime: str,
    sidecar: dict,
    is_encrypted: bool,
) -> dict:
    variant_ext = get_variant_extension(is_encrypted)
    playback_ext = ".mp4" if not is_encrypted else variant_ext
    thumb_ext = ".jpg" if not is_encrypted else variant_ext
    title_default = os.path.splitext(basename)[0].replace("_", " ").title()
    meta = {
        "media_type": "video",
        "id": video_id,
        "filename": basename,
        "url": f"/galleries/{gallery_id}/{video_id}.html",
        "thumbnail_path": f"/galleries/{gallery_id}/thumbnail/{video_id}{thumb_ext}",
        "playback_path": f"/galleries/{gallery_id}/video/{video_id}{playback_ext}",
        "title": sidecar.get("title", title_default),
        "caption": sidecar.get("caption", ""),
        "tags": sidecar.get("tags", []) if isinstance(sidecar.get("tags"), list) else [],
        "lat": None,
        "lon": None,
        "exif": {"DateTimeOriginal": exif_datetime},
    }
    if is_encrypted:
        meta["metadata_path"] = (
            f"/galleries/{gallery_id}/{METADATA_VARIANT_DIR}/{video_id}{METADATA_BLOB_EXTENSION}"
        )
    return meta


def check_video_outputs(
    source_path: str,
    gallery_id: str,
    video_id: str,
    is_encrypted: bool,
) -> bool:
    source_mtimes = [
        os.path.getmtime(source_path),
        os.path.getmtime("config.yaml"),
        os.path.getmtime(os.path.join(config["source_path"], gallery_id, "gallery.yaml")),
    ]
    latest_source_mtime = max(source_mtimes)
    variant_ext = get_variant_extension(is_encrypted)
    thumb_ext = ".jpg" if not is_encrypted else variant_ext
    play_ext = ".mp4" if not is_encrypted else variant_ext

    thumb_out = os.path.join(
        config["output_path"],
        "public_html",
        "galleries",
        gallery_id,
        "thumbnail",
        f"{video_id}{thumb_ext}",
    )
    play_out = os.path.join(
        config["output_path"],
        "public_html",
        "galleries",
        gallery_id,
        "video",
        f"{video_id}{play_ext}",
    )
    meta_out = os.path.join(
        config["output_path"], "metadata", gallery_id, f"{video_id}.json"
    )
    for p in (thumb_out, play_out, meta_out):
        if not os.path.exists(p):
            return False
        if os.path.getmtime(p) < latest_source_mtime:
            return False
    if is_encrypted:
        blob_out = os.path.join(
            config["output_path"],
            "public_html",
            "galleries",
            gallery_id,
            METADATA_VARIANT_DIR,
            f"{video_id}{METADATA_BLOB_EXTENSION}",
        )
        if not os.path.exists(blob_out):
            return False
        if os.path.getmtime(blob_out) < latest_source_mtime:
            return False
    return True


def run_ffmpeg_thumbnail(
    src: str,
    seek_sec: float,
    out_path: str,
    thumb_max: int,
) -> None:
    vf = f"scale={thumb_max}:{thumb_max}:force_original_aspect_ratio=decrease"
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(seek_sec),
        "-i",
        src,
        "-vframes",
        "1",
        "-vf",
        vf,
        "-q:v",
        str(FFMPEG_THUMB_QSCALE),
        out_path,
    ]
    subprocess.run(cmd, check=True)


def run_ffmpeg_transcode(
    src: str,
    out_path: str,
    out_w: int,
    out_h: int,
    video_bitrate_bps: int,
) -> None:
    vf = build_scale_vf(out_w, out_h)
    cmd = (
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            src,
            "-t",
            str(VIDEO_MAX_DURATION_SECONDS),
            "-vf",
            vf,
        ]
        + build_libx264_codec_args(video_bitrate_bps)
        + build_aac_audio_args()
        + ["-movflags", "+faststart", out_path]
    )
    subprocess.run(cmd, check=True)


def encrypt_variant_file(
    plaintext_path: str,
    output_path: str,
    gallery_id: str,
    video_id: str,
    password: str,
    nonce_prefix: str,
    variant_label: str,
) -> None:
    key = derive_encryption_params(gallery_id, video_id, password)
    nonce_material = (
        f"{nonce_prefix}|{gallery_id}|{video_id}|{variant_label}"
    ).encode("utf-8")
    encrypted_data = encrypt_file(plaintext_path, key, nonce_material)
    with open(output_path, "wb") as f:
        f.write(encrypted_data)


def process_video(
    video_path: str,
    gallery_id: str,
    gallery_config: dict,
    progress: Progress | None = None,
    video_number: int | None = None,
    total_videos: int | None = None,
) -> dict:
    basename = os.path.basename(video_path)
    is_encrypted = gallery_config.get("encrypted", False)
    video_id = generate_video_id(basename, gallery_id, is_encrypted)

    if check_video_outputs(video_path, gallery_id, video_id, is_encrypted):
        if progress and video_number and total_videos:
            task = progress.add_task(
                f"[green]✓ Skipping {basename}[/] ({video_number}/{total_videos})",
                total=100,
            )
            progress.update(task, completed=100)
            progress.remove_task(task)
        meta_path = os.path.join(
            config["output_path"], "metadata", gallery_id, f"{video_id}.json"
        )
        with open(meta_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if is_encrypted:
            public_meta = create_public_video_metadata_dict(existing)
            if existing != public_meta:
                with open(meta_path, "w", encoding="utf-8") as mf:
                    json.dump(public_meta, mf, indent=2)
            return public_meta
        return existing

    if progress and video_number and total_videos:
        task = progress.add_task(
            f"[cyan]{basename}[/] ({video_number}/{total_videos})",
            total=100,
        )
        progress.update(task, completed=5)

    probe = ffprobe_video(video_path)
    iw, ih, duration_raw, creation_tag = parse_ffprobe_dimensions_and_duration(probe)
    out_w, out_h = compute_output_dimensions(iw, ih)
    video_bps = select_video_bitrate_bps(out_h)
    clamped_d = clamp_duration_seconds(duration_raw)
    seek = poster_seek_seconds(duration_raw)

    sidecar = get_image_metadata(video_path)
    dt_norm = normalize_creation_time_tag(creation_tag)
    exif_dt = dt_norm if dt_norm else mtime_exif_datetime(video_path)

    output_metadata = create_video_metadata_dict(
        basename, video_id, gallery_id, exif_dt, sidecar, is_encrypted
    )

    thumb_dir = os.path.join(
        config["output_path"], "public_html", "galleries", gallery_id, "thumbnail"
    )
    video_dir = os.path.join(
        config["output_path"], "public_html", "galleries", gallery_id, "video"
    )
    os.makedirs(thumb_dir, exist_ok=True)
    os.makedirs(video_dir, exist_ok=True)

    variant_ext = get_variant_extension(is_encrypted)
    thumb_final = os.path.join(
        thumb_dir,
        f"{video_id}{'.jpg' if not is_encrypted else variant_ext}",
    )
    play_final = os.path.join(
        video_dir,
        f"{video_id}{'.mp4' if not is_encrypted else variant_ext}",
    )

    thumb_max = int(config["image_sizes"]["thumbnail"])

    if is_encrypted:
        thumb_tmp = os.path.join(thumb_dir, f"{video_id}{TEMP_THUMB_PLAINTEXT_SUFFIX}")
        play_tmp = os.path.join(video_dir, f"{video_id}{TEMP_VIDEO_PLAINTEXT_SUFFIX}")
        try:
            run_ffmpeg_thumbnail(video_path, seek, thumb_tmp, thumb_max)
            if progress:
                progress.update(task, completed=35)
            run_ffmpeg_transcode(video_path, play_tmp, out_w, out_h, video_bps)
            if progress:
                progress.update(task, completed=65)

            encrypt_variant_file(
                thumb_tmp,
                thumb_final,
                gallery_id,
                video_id,
                gallery_config["password"],
                GCM_NONCE_MATERIAL_PREFIX_VIDEO_THUMBNAIL,
                "thumbnail",
            )
            encrypt_variant_file(
                play_tmp,
                play_final,
                gallery_id,
                video_id,
                gallery_config["password"],
                GCM_NONCE_MATERIAL_PREFIX_VIDEO_PLAYBACK,
                "playback",
            )
            write_encrypted_video_metadata_blob(
                output_metadata, gallery_id, gallery_config["password"]
            )
        finally:
            for tmp in (thumb_tmp, play_tmp):
                if os.path.exists(tmp):
                    os.unlink(tmp)
    else:
        run_ffmpeg_thumbnail(video_path, seek, thumb_final, thumb_max)
        if progress:
            progress.update(task, completed=35)
        run_ffmpeg_transcode(video_path, play_final, out_w, out_h, video_bps)
        if progress:
            progress.update(task, completed=65)

    metadata_dir = os.path.join(config["output_path"], "metadata", gallery_id)
    os.makedirs(metadata_dir, exist_ok=True)
    meta_path = os.path.join(metadata_dir, f"{video_id}.json")
    to_write = (
        create_public_video_metadata_dict(output_metadata)
        if is_encrypted
        else output_metadata
    )
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(to_write, f, indent=2)

    if progress:
        progress.update(task, completed=100)
        progress.remove_task(task)

    return to_write


def list_gallery_videos(gallery_path: str) -> list[str]:
    if not os.path.isdir(gallery_path):
        return []
    names = sorted(
        f
        for f in os.listdir(gallery_path)
        if f.lower().endswith(SUPPORTED_VIDEO_EXTENSIONS)
    )
    return [os.path.join(gallery_path, f) for f in names]


def process_gallery_videos(gallery_name: str) -> tuple[int, int]:
    success = failed = 0
    gallery_path = os.path.join(config["source_path"], gallery_name)
    if not os.path.isdir(gallery_path):
        return success, failed

    gallery_yaml = os.path.join(gallery_path, "gallery.yaml")
    with open(gallery_yaml, "r", encoding="utf-8") as f:
        gallery_config = yaml.safe_load(f)

    if gallery_config.get("encrypted", False):
        from image_processor import clean_encrypted_variant_outputs

        clean_encrypted_variant_outputs(gallery_name)

    videos = list_gallery_videos(gallery_path)
    if not videos:
        return success, failed

    console.print(f"\n[bold yellow]⚡ Processing videos: {gallery_name}[/]")
    console.print(f"  • Found [green]{len(videos)}[/] video(s)")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description: <50}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=True,
    ) as progress:
        overall = progress.add_task("[cyan]Videos", total=len(videos))
        for idx, vp in enumerate(videos, 1):
            try:
                process_video(
                    vp,
                    gallery_name,
                    gallery_config,
                    progress,
                    idx,
                    len(videos),
                )
                success += 1
            except Exception as e:
                console.print(f"[red]Error processing {vp}: {e}[/]")
                failed += 1
            progress.advance(overall)

    return success, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Process gallery videos.")
    parser.add_argument("--all", action="store_true", help="Process all galleries")
    parser.add_argument("gallery", nargs="?", help="Gallery directory name")
    args = parser.parse_args()

    title = Text("Gallery Video Processor", style="bold cyan")
    console.print(Panel(title, border_style="cyan"))

    if not args.all and not args.gallery:
        parser.print_help()
        sys.exit(1)

    if args.all:
        gallery_paths = [
            g
            for g in os.listdir(config["source_path"])
            if os.path.isdir(os.path.join(config["source_path"], g))
        ]
    else:
        gp = os.path.join(config["source_path"], args.gallery)
        gallery_paths = [args.gallery] if os.path.isdir(gp) else []

    total_ok = total_fail = 0
    for gname in sorted(gallery_paths):
        ok, fail = process_gallery_videos(gname)
        total_ok += ok
        total_fail += fail

    console.print("\n[bold]Video processing summary[/]")
    console.print(f"  ✓ Success: [green]{total_ok}[/]")
    if total_fail:
        console.print(f"  ✗ Failed: [red]{total_fail}[/]")
        sys.exit(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/]")
        sys.exit(130)
