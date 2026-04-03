"""Unit tests for gengallery argparse wiring (no editable install required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gengallery.cli import build_parser, dispatch, main, parse_args
from gengallery.commands import init as cmd_init
from gengallery.commands import push as cmd_push
from gengallery.commands import serve as cmd_serve
from gengallery.commands import update as cmd_update
from gengallery.constants import DEFAULT_SERVE_PORT


def test_top_level_help_exits_zero():
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--help"])
    assert exc_info.value.code == 0


def test_init_yields_init_run():
    args = parse_args(["init"])
    assert args.handler is cmd_init.run
    assert getattr(args, "path", None) is None


def test_init_with_path_normalized():
    args = parse_args(["init", "myproj"])
    assert args.path == "myproj"


def test_push_ssh_yields_push_run():
    args = parse_args(["push", "ssh"])
    assert args.handler is cmd_push.run


def test_serve_port_parsed():
    args = parse_args(["serve", "--port", "9000"])
    assert args.handler is cmd_serve.run
    assert args.port == 9000


def test_serve_default_port():
    args = parse_args(["serve"])
    assert args.port == DEFAULT_SERVE_PORT


def test_update_yields_update_run():
    args = parse_args(["update"])
    assert args.handler is cmd_update.run


def test_unknown_subcommand_exits_nonzero():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["not-a-command"])
    assert exc_info.value.code != 0


def test_push_missing_provider_exits_nonzero():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["push"])
    assert exc_info.value.code != 0


def test_dispatch_init_stub_succeeds(tmp_path: Path):
    args = parse_args(["init"])
    assert dispatch(args, cwd=tmp_path) == 0


def test_dispatch_passes_path_object_to_handler(tmp_path: Path):
    captured: dict[str, object] = {}

    def recorder(project_root, args):
        captured["root"] = project_root
        return 0

    args = parse_args(["init", "rel"])
    args.handler = recorder
    assert dispatch(args, cwd=tmp_path) == 0
    assert captured["root"] == (tmp_path / "rel").resolve()


def test_main_uses_sys_argv_when_argv_omitted(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["gengallery", "init", "--help"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
