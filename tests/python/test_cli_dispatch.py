"""CLI main/dispatch integration with temp project trees."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gengallery.cli import dispatch, main


def _write_minimal_project(root: Path, *, with_public_html: bool) -> None:
    gal = root / "galleries"
    gal.mkdir()
    cfg = root / "config.yaml"
    cfg.write_text(
        "source_path: ./galleries\n"
        "output_path: ./export\n"
        "ssh:\n"
        "  post_sync_commands:\n"
        "    - 'chown -R {user}:{group} {destination}'\n",
        encoding="utf-8",
    )
    exp = root / "export"
    exp.mkdir(exist_ok=True)
    if with_public_html:
        (exp / "public_html").mkdir()


def test_main_update_valid_project_exits_zero(tmp_path: Path, monkeypatch):
    _write_minimal_project(tmp_path, with_public_html=False)
    monkeypatch.chdir(tmp_path)
    # Full pipeline needs real galleries/media; this test only checks CLI validation + dispatch.
    monkeypatch.setattr("gengallery.commands.update.run_update", lambda _root, _cfg: None)
    monkeypatch.setattr(sys, "argv", ["gengallery", "update"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_main_serve_missing_public_html_exits_one(tmp_path: Path, monkeypatch, capsys):
    _write_minimal_project(tmp_path, with_public_html=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gengallery", "serve"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "gengallery update" in err


def test_main_serve_with_public_html_exits_zero(tmp_path: Path, monkeypatch):
    _write_minimal_project(tmp_path, with_public_html=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gengallery.commands.serve.run_serve", lambda *_a, **_k: None)
    monkeypatch.setattr(sys, "argv", ["gengallery", "serve"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_dispatch_push_ssh_validates_config(tmp_path: Path, monkeypatch):
    _write_minimal_project(tmp_path, with_public_html=True)
    monkeypatch.setattr("gengallery.commands.push.run_deploy", lambda *_a, **_k: None)
    from gengallery.cli import parse_args

    args = parse_args(["push", "ssh"])
    assert dispatch(args, cwd=tmp_path) == 0


def test_main_push_aws_argparse_failure(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["gengallery", "push", "aws"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0
