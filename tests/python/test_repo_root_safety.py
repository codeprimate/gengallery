"""Guardrails: destructive CLI tests must not use the real repository tree as cwd/target."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _is_descendant(child: Path, ancestor: Path) -> bool:
    try:
        child.resolve().relative_to(ancestor.resolve())
        return True
    except ValueError:
        return False


def test_pytest_tmp_path_is_not_inside_repository(tmp_path: Path) -> None:
    assert not _is_descendant(tmp_path, REPO_ROOT)
