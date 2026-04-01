"""Unit tests for bin/video_encoding.py (no ffmpeg)."""

import os
import sys
import tempfile

import pytest

BIN_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "bin"))
if BIN_PATH not in sys.path:
    sys.path.insert(0, BIN_PATH)

from video_encoding import (  # noqa: E402
    AUDIO_BITRATE_AAC_BPS,
    VIDEO_BITRATE_BPS_1080,
    VIDEO_BITRATE_BPS_720,
    VIDEO_MAX_DURATION_SECONDS,
    VIDEO_VBV_BUF_SIZE_MULTIPLIER,
    build_aac_audio_args,
    build_libx264_codec_args,
    build_scale_vf,
    build_x264_vbv_args,
    clamp_duration_seconds,
    compute_output_dimensions,
    mtime_exif_datetime,
    normalize_creation_time_tag,
    poster_seek_seconds,
    select_video_bitrate_bps,
)


def test_clamp_duration_seconds():
    assert clamp_duration_seconds(0) == 0.0
    assert clamp_duration_seconds(30) == 30.0
    assert clamp_duration_seconds(200) == float(VIDEO_MAX_DURATION_SECONDS)


def test_poster_seek_seconds():
    assert poster_seek_seconds(0.05) == 0.0
    assert poster_seek_seconds(10) == 1.0
    assert poster_seek_seconds(5) == 0.5


def test_compute_output_dimensions_upscale():
    w, h = compute_output_dimensions(640, 480)
    assert h == 720
    assert w % 2 == 0 and h % 2 == 0


def test_compute_output_dimensions_downscale():
    w, h = compute_output_dimensions(3840, 2160)
    assert h == 1080
    assert w % 2 == 0


def test_compute_output_dimensions_even_middle():
    w, h = compute_output_dimensions(1001, 801)
    assert w == 1000
    assert h == 800


def test_compute_output_dimensions_invalid():
    with pytest.raises(ValueError):
        compute_output_dimensions(0, 720)


def test_select_video_bitrate_bps():
    assert select_video_bitrate_bps(720) == VIDEO_BITRATE_BPS_720
    assert select_video_bitrate_bps(721) == VIDEO_BITRATE_BPS_1080


def test_build_x264_vbv_args():
    args = build_x264_vbv_args(3_000_000)
    assert "-b:v" in args
    assert args[args.index("-b:v") + 1] == "3000000"
    assert args[args.index("-bufsize") + 1] == str(3_000_000 * VIDEO_VBV_BUF_SIZE_MULTIPLIER)


def test_build_libx264_codec_args_contains_preset():
    args = build_libx264_codec_args(5_000_000)
    assert "-preset" in args
    assert args[args.index("-preset") + 1] == "medium"
    assert "-profile:v" in args


def test_build_aac_audio_args():
    args = build_aac_audio_args()
    assert "-c:a" in args and "aac" in args
    assert args[args.index("-b:a") + 1] == str(AUDIO_BITRATE_AAC_BPS)


def test_build_scale_vf():
    assert build_scale_vf(1280, 720) == "scale=1280:720"


def test_normalize_creation_time_tag():
    assert normalize_creation_time_tag(None) is None
    assert normalize_creation_time_tag("2024-01-15T12:30:45.000000Z") == "2024:01:15 12:30:45"
    assert normalize_creation_time_tag("2024-01-15 12:30:45") == "2024:01:15 12:30:45"


def test_mtime_exif_datetime():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        path = tmp.name
    try:
        s = mtime_exif_datetime(path)
        assert len(s) == 19
        assert s[4] == ":" and s[7] == ":"
    finally:
        os.unlink(path)
