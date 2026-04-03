"""Tests for SSH deploy argv construction."""

from __future__ import annotations

from pathlib import Path

from gengallery.services.deploy_ssh import build_rsync_argv, build_ssh_argv


def test_build_rsync_argv_trailing_slashes():
    argv = build_rsync_argv(
        Path("/tmp/export/public_html"),
        "admin",
        "example.com",
        "/data/gallery/",
    )
    assert argv[0] == "rsync"
    assert "-az" in argv
    assert "--progress" in argv
    assert "--delete" in argv
    assert argv[-2].endswith("/")
    assert argv[-1] == "admin@example.com:/data/gallery/"


def test_build_ssh_argv_remote_command_single_argument():
    argv = build_ssh_argv("u", "h.example", "chown -R u:g /path")
    assert argv == ["ssh", "u@h.example", "chown -R u:g /path"]
