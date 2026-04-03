"""Unit tests for npm install helper (subprocess boundaries)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gengallery.errors import CliUserError
from gengallery.services.npm_install import (
    MSG_NPM_INSTALL_FAILED_PREFIX,
    MSG_NPM_NOT_FOUND,
    NPM_ARG_INSTALL,
    NPM_EXECUTABLE,
    run_npm_install,
)


def test_run_npm_install_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(
        argv: list[str],
        *,
        cwd: Path | str | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        assert argv == [NPM_EXECUTABLE, NPM_ARG_INSTALL]
        assert cwd == tmp_path.resolve()
        assert timeout is not None
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("gengallery.services.npm_install.subprocess.run", fake_run)
    run_npm_install(tmp_path)


def test_run_npm_install_nonzero_raises_cli_user_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(
        argv: list[str],
        *,
        cwd: Path | str | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "", "simulated npm failure")

    monkeypatch.setattr("gengallery.services.npm_install.subprocess.run", fake_run)
    with pytest.raises(CliUserError) as exc_info:
        run_npm_install(tmp_path)
    assert MSG_NPM_INSTALL_FAILED_PREFIX in exc_info.value.message
    assert "simulated npm failure" in exc_info.value.message


def test_run_npm_install_missing_npm_raises_cli_user_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(
        *args: object,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError()

    monkeypatch.setattr("gengallery.services.npm_install.subprocess.run", fake_run)
    with pytest.raises(CliUserError) as exc_info:
        run_npm_install(tmp_path)
    assert exc_info.value.message == MSG_NPM_NOT_FOUND
