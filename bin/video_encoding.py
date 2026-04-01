"""
Video encoding parameters and ffmpeg argument builders.

Constants are module-level for later optional override from config.yaml.
"""

from __future__ import annotations

# Duration / layout
VIDEO_MAX_DURATION_SECONDS = 120
VIDEO_MIN_HEIGHT_PX = 720
VIDEO_MAX_HEIGHT_PX = 1080

# Video tiers (bits per second)
VIDEO_BITRATE_BPS_720 = 3_000_000
VIDEO_BITRATE_BPS_1080 = 5_000_000

# Audio
AUDIO_BITRATE_AAC_BPS = 128_000

# x264 VBV
VIDEO_VBV_BUF_SIZE_MULTIPLIER = 2

# Poster frame seek: min(POSTER_MIN_SECONDS, duration * POSTER_FRACTION_OF_DURATION)
POSTER_MIN_SECONDS = 1.0
POSTER_FRACTION_OF_DURATION = 0.1
POSTER_DURATION_FLOOR_FOR_FRACTION = 0.1

# x264
X264_PRESET = "medium"
X264_PROFILE = "high"
X264_PIX_FMT = "yuv420p"


def clamp_duration_seconds(duration: float) -> float:
    """Clamp source duration to the max encode length."""
    if duration <= 0:
        return 0.0
    return min(float(duration), float(VIDEO_MAX_DURATION_SECONDS))


def poster_seek_seconds(duration_seconds: float) -> float:
    """Timestamp (seconds) to extract the poster JPEG from the source video."""
    clamped = clamp_duration_seconds(duration_seconds)
    if clamped < POSTER_DURATION_FLOOR_FOR_FRACTION:
        return 0.0
    return min(POSTER_MIN_SECONDS, clamped * POSTER_FRACTION_OF_DURATION)


def compute_output_dimensions(width: int, height: int) -> tuple[int, int]:
    """
    Apply height clamp (720–1080) and even dimensions.

    Returns:
        (out_width, out_height) in pixels, both even and >= 2.
    """
    if width < 1 or height < 1:
        raise ValueError("width and height must be positive")

    if height < VIDEO_MIN_HEIGHT_PX:
        out_h = VIDEO_MIN_HEIGHT_PX
        out_w = max(2, int(round(width * out_h / height)))
    elif height > VIDEO_MAX_HEIGHT_PX:
        out_h = VIDEO_MAX_HEIGHT_PX
        out_w = max(2, int(round(width * out_h / height)))
    else:
        out_w, out_h = width, height

    out_w = max(2, out_w - (out_w % 2))
    out_h = max(2, out_h - (out_h % 2))
    return out_w, out_h


def select_video_bitrate_bps(output_height_px: int) -> int:
    """3 Mbps for 720p-tier height; 5 Mbps above 720."""
    if output_height_px <= VIDEO_MIN_HEIGHT_PX:
        return VIDEO_BITRATE_BPS_720
    return VIDEO_BITRATE_BPS_1080


def build_x264_vbv_args(video_bitrate_bps: int) -> list[str]:
    """Return ffmpeg libx264 -b:v, -maxrate, -bufsize arguments."""
    maxrate = video_bitrate_bps
    bufsize = int(video_bitrate_bps * VIDEO_VBV_BUF_SIZE_MULTIPLIER)
    return [
        "-b:v",
        str(video_bitrate_bps),
        "-maxrate",
        str(maxrate),
        "-bufsize",
        str(bufsize),
    ]


def build_libx264_codec_args(video_bitrate_bps: int) -> list[str]:
    """Video codec chain: libx264 with preset, profile, pix_fmt, and VBV."""
    return (
        [
            "-c:v",
            "libx264",
            "-preset",
            X264_PRESET,
            "-profile:v",
            X264_PROFILE,
            "-pix_fmt",
            X264_PIX_FMT,
        ]
        + build_x264_vbv_args(video_bitrate_bps)
    )


def build_aac_audio_args() -> list[str]:
    """AAC audio encoding arguments."""
    return [
        "-c:a",
        "aac",
        "-b:a",
        str(AUDIO_BITRATE_AAC_BPS),
    ]


def build_scale_vf(output_w: int, output_h: int) -> str:
    """Video filter scale to explicit even dimensions."""
    return f"scale={output_w}:{output_h}"


def normalize_creation_time_tag(raw: str | None) -> str | None:
    """
    Normalize ffprobe creation_time to EXIF-style 'YYYY:mm:dd HH:MM:SS'.

    Returns None if input is missing or unusable.
    """
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1].strip()
    if "+" in s:
        s = s.split("+", 1)[0].strip()
    s = s.replace("T", " ")
    if "." in s:
        s = s.split(".", 1)[0].strip()
    tokens = s.split()
    if len(tokens) < 2:
        return None
    date_part = tokens[0].replace("-", ":")
    time_part = tokens[1]
    date_bits = date_part.split(":")
    time_bits = time_part.split(":")
    if len(date_bits) != 3:
        return None
    try:
        y, mo, d = (int(date_bits[i]) for i in range(3))
        h = int(time_bits[0]) if len(time_bits) > 0 else 0
        mi = int(time_bits[1]) if len(time_bits) > 1 else 0
        sec = int(time_bits[2]) if len(time_bits) > 2 else 0
        return f"{y:04d}:{mo:02d}:{d:02d} {h:02d}:{mi:02d}:{sec:02d}"
    except ValueError:
        return None


def mtime_exif_datetime(file_path: str) -> str:
    """EXIF-style datetime from file mtime."""
    import os
    from datetime import datetime

    m = os.path.getmtime(file_path)
    return datetime.fromtimestamp(m).strftime("%Y:%m:%d %H:%M:%S")
