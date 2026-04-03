"""Run ``npm install`` in a gallery project (Tailwind and related JS deps)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gengallery.errors import CliUserError

NPM_EXECUTABLE = "npm"
NPM_ARG_INSTALL = "install"
NPM_INSTALL_TIMEOUT_SECONDS = 600

MSG_NPM_NOT_FOUND = (
    "Cannot install npm dependencies: `npm` was not found on PATH. "
    "Install Node.js from https://nodejs.org/ (it includes npm), then run `gengallery init` again "
    "or run `npm install` in the project directory."
)
MSG_NPM_INSTALL_TIMEOUT = (
    f"`npm {NPM_ARG_INSTALL}` exceeded {NPM_INSTALL_TIMEOUT_SECONDS} seconds and was stopped."
)
MSG_NPM_INSTALL_FAILED_PREFIX = "`npm install` failed:"

_STDERR_SNIPPET_MAX_CHARS = 4000


def run_npm_install(project_root: Path) -> None:
    """
    Run ``npm install`` with cwd ``project_root``.

    Raises:
        CliUserError: If ``npm`` is missing, the install times out, or exit code is non-zero.
            stderr/stdout are attached (truncated).
    """
    root = project_root.resolve()
    argv = [NPM_EXECUTABLE, NPM_ARG_INSTALL]
    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=NPM_INSTALL_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise CliUserError(MSG_NPM_NOT_FOUND) from exc
    except subprocess.TimeoutExpired as exc:
        raise CliUserError(MSG_NPM_INSTALL_TIMEOUT) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        if len(detail) > _STDERR_SNIPPET_MAX_CHARS:
            detail = detail[:_STDERR_SNIPPET_MAX_CHARS] + "\n… (truncated)"
        suffix = f"\n{detail}" if detail else ""
        raise CliUserError(f"{MSG_NPM_INSTALL_FAILED_PREFIX}{suffix}") from None
