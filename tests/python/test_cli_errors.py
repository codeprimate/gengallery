"""End-to-end CLI user errors (complements test_pathing validators and test_cli_dispatch)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gengallery.cli import main


def test_main_update_without_config_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gengallery", "update"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0


def test_main_push_ssh_missing_post_sync_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gal = tmp_path / "galleries"
    gal.mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "source_path: ./galleries\n"
        "output_path: ./export\n"
        "ssh: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "export").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gengallery", "push", "ssh"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0


def test_main_push_ssh_missing_ssh_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gal = tmp_path / "galleries"
    gal.mkdir()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "source_path: ./galleries\n"
        "output_path: ./export\n",
        encoding="utf-8",
    )
    (tmp_path / "export").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gengallery", "push", "ssh"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0
