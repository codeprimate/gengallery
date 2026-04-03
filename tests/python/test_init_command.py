"""gengallery init: mkdir, conflicts, scaffold materialization."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gengallery import __version__
from gengallery.cli import dispatch, main, parse_args
from gengallery.commands.init import (
    INIT_MSG_LEAD_IN,
    INIT_MSG_NPM_INSTALLED,
    INIT_MSG_NPM_INSTALLING,
    INIT_MSG_SUCCESS,
    INIT_MSG_WROTE_SCAFFOLD,
)
from gengallery.constants import (
    CLI_APP_NAME,
    CONFIG_FILENAME,
    GALLERIES_DIRNAME,
    PACKAGE_JSON_FILENAME,
    SCAFFOLD_EXAMPLE_GALLERY_DIRNAME,
    TEMPLATES_DIRNAME,
)
from gengallery.errors import CliUserError
from gengallery.services.init_scaffold import (
    MSG_INIT_CONFLICT_CONFIG,
    MSG_INIT_CONFLICT_GALLERIES,
    MSG_INIT_CONFLICT_PACKAGE_JSON,
    MSG_INIT_CONFLICT_TEMPLATES,
    run_init,
)


def test_init_dispatch_creates_scaffold_in_empty_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("gengallery.commands.init.run_npm_install", lambda _p: None)
    monkeypatch.chdir(tmp_path)
    args = parse_args(["init"])
    assert dispatch(args, cwd=tmp_path) == 0
    out = capsys.readouterr().out
    assert CLI_APP_NAME in out
    assert f"v{__version__}" in out
    assert INIT_MSG_LEAD_IN in out
    # Rich may wrap long paths across lines; banner path is still present.
    assert str(tmp_path.resolve()) in "".join(out.splitlines())
    assert INIT_MSG_WROTE_SCAFFOLD in out
    assert INIT_MSG_NPM_INSTALLING in out
    assert INIT_MSG_NPM_INSTALLED in out
    assert INIT_MSG_SUCCESS in out
    assert (tmp_path / CONFIG_FILENAME).is_file()
    assert (tmp_path / PACKAGE_JSON_FILENAME).is_file()
    gal = tmp_path / GALLERIES_DIRNAME / SCAFFOLD_EXAMPLE_GALLERY_DIRNAME
    assert (gal / "gallery.yaml").is_file()
    assert (gal / "lightbulb.webp").is_file()
    assert (gal / "lightbulb.yaml").is_file()
    assert (tmp_path / TEMPLATES_DIRNAME / "index.html.jinja").is_file()


def test_init_main_nested_path_creates_parents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("gengallery.commands.init.run_npm_install", lambda _p: None)
    nested = tmp_path / "a" / "b" / "newproj"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gengallery", "init", str(nested.relative_to(tmp_path))])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert nested.is_dir()
    assert (nested / CONFIG_FILENAME).is_file()
    out = capsys.readouterr().out
    assert CLI_APP_NAME in out
    assert f"v{__version__}" in out
    assert INIT_MSG_LEAD_IN in out
    assert str(nested.resolve()) in "".join(out.splitlines())
    assert "Created project directory:" in out
    assert INIT_MSG_SUCCESS in out


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
    assert run_init(tmp_path) > 0
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


def test_run_init_rejects_existing_package_json(tmp_path: Path) -> None:
    (tmp_path / PACKAGE_JSON_FILENAME).write_text("{}\n", encoding="utf-8")
    with pytest.raises(CliUserError) as excinfo:
        run_init(tmp_path)
    assert excinfo.value.message == MSG_INIT_CONFLICT_PACKAGE_JSON


def test_init_run_npm_install_receives_resolved_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Path] = []

    def capture(root: Path) -> None:
        seen.append(root)

    monkeypatch.setattr("gengallery.commands.init.run_npm_install", capture)
    monkeypatch.chdir(tmp_path)
    args = parse_args(["init", "myproj"])
    assert dispatch(args, cwd=tmp_path) == 0
    assert len(seen) == 1
    assert seen[0] == (tmp_path / "myproj").resolve()


def test_run_init_requires_directory(tmp_path: Path) -> None:
    file_only = tmp_path / "not_a_dir"
    file_only.write_text("x", encoding="utf-8")
    with pytest.raises(AssertionError):
        run_init(file_only)
