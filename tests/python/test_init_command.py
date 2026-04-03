"""gengallery init: mkdir, conflicts, scaffold materialization."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gengallery.cli import dispatch, main, parse_args
from gengallery.constants import (
    CONFIG_FILENAME,
    GALLERIES_DIRNAME,
    SCAFFOLD_EXAMPLE_GALLERY_DIRNAME,
    TEMPLATES_DIRNAME,
)
from gengallery.errors import CliUserError
from gengallery.services.init_scaffold import (
    MSG_INIT_CONFLICT_CONFIG,
    MSG_INIT_CONFLICT_GALLERIES,
    MSG_INIT_CONFLICT_TEMPLATES,
    run_init,
)


def test_init_dispatch_creates_scaffold_in_empty_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    args = parse_args(["init"])
    assert dispatch(args, cwd=tmp_path) == 0
    assert (tmp_path / CONFIG_FILENAME).is_file()
    gal = tmp_path / GALLERIES_DIRNAME / SCAFFOLD_EXAMPLE_GALLERY_DIRNAME
    assert (gal / "gallery.yaml").is_file()
    assert (tmp_path / TEMPLATES_DIRNAME / "index.html.jinja").is_file()


def test_init_main_nested_path_creates_parents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = tmp_path / "a" / "b" / "newproj"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gengallery", "init", str(nested.relative_to(tmp_path))])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert nested.is_dir()
    assert (nested / CONFIG_FILENAME).is_file()


def test_init_cli_user_error_when_config_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / CONFIG_FILENAME).write_text("x: 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gengallery", "init"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_init_stderr_mentions_conflict_when_galleries_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / GALLERIES_DIRNAME).mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gengallery", "init"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert GALLERIES_DIRNAME in capsys.readouterr().err


def test_init_stderr_mentions_conflict_when_templates_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / TEMPLATES_DIRNAME).mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gengallery", "init"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert TEMPLATES_DIRNAME in capsys.readouterr().err


def test_run_init_second_time_fails(tmp_path: Path) -> None:
    assert run_init(tmp_path) == 0
    with pytest.raises(CliUserError) as excinfo:
        run_init(tmp_path)
    assert excinfo.value.message == MSG_INIT_CONFLICT_CONFIG


def test_run_init_rejects_existing_galleries(tmp_path: Path) -> None:
    (tmp_path / GALLERIES_DIRNAME).mkdir()
    with pytest.raises(CliUserError) as excinfo:
        run_init(tmp_path)
    assert excinfo.value.message == MSG_INIT_CONFLICT_GALLERIES


def test_run_init_rejects_existing_templates(tmp_path: Path) -> None:
    (tmp_path / TEMPLATES_DIRNAME).mkdir()
    with pytest.raises(CliUserError) as excinfo:
        run_init(tmp_path)
    assert excinfo.value.message == MSG_INIT_CONFLICT_TEMPLATES


def test_run_init_requires_directory(tmp_path: Path) -> None:
    file_only = tmp_path / "not_a_dir"
    file_only.write_text("x", encoding="utf-8")
    with pytest.raises(AssertionError):
        run_init(file_only)
