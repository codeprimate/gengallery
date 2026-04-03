"""CLI dispatch: project root resolution for each command × path form."""

from __future__ import annotations

from pathlib import Path

import pytest

from gengallery.cli import dispatch, parse_args

PROJECT_SUBDIR = "nested_prj"


def _write_minimal_project(root: Path, *, with_public_html: bool) -> None:
    gal = root / "galleries"
    gal.mkdir(parents=True)
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


def _target_root(tmp_path: Path, path_form: str) -> Path:
    if path_form == "omitted":
        return tmp_path
    return tmp_path / PROJECT_SUBDIR


def _argv(command: str, path_form: str, tmp_path: Path) -> list[str]:
    if command == "init":
        base = ["init"]
    elif command == "update":
        base = ["update"]
    elif command == "serve":
        base = ["serve"]
    elif command == "push_ssh":
        base = ["push", "ssh"]
    else:
        raise AssertionError(command)

    if path_form == "omitted":
        return base
    if path_form == "relative":
        return base + [PROJECT_SUBDIR]
    if path_form == "absolute":
        return base + [str((tmp_path / PROJECT_SUBDIR).resolve())]
    raise AssertionError(path_form)


@pytest.mark.parametrize("path_form", ["omitted", "relative", "absolute"])
@pytest.mark.parametrize("command", ["init", "update", "serve", "push_ssh"])
def test_dispatch_resolves_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    path_form: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    target = _target_root(tmp_path, path_form)
    if command != "init":
        _write_minimal_project(target, with_public_html=(command in ("serve", "push_ssh")))

    captured: list[Path] = []

    def capture_run(project_root: Path, _args) -> int:
        captured.append(project_root)
        return 0

    if command == "init":
        monkeypatch.setattr("gengallery.commands.init.run", capture_run)
    elif command == "update":
        monkeypatch.setattr("gengallery.commands.update.run", capture_run)
    elif command == "serve":
        monkeypatch.setattr("gengallery.commands.serve.run", capture_run)
    else:
        monkeypatch.setattr("gengallery.commands.push.run", capture_run)

    argv = _argv(command, path_form, tmp_path)
    args = parse_args(argv)
    assert dispatch(args, cwd=tmp_path) == 0
    assert len(captured) == 1
    assert captured[0] == target.resolve()
