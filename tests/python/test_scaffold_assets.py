"""Scaffold iteration and materialization from packaged assets."""

from __future__ import annotations

from pathlib import Path

import pytest

from gengallery.constants import (
    CONFIG_FILENAME,
    GALLERIES_DIRNAME,
    SCAFFOLD_EXAMPLE_GALLERY_DIRNAME,
    TEMPLATES_DIRNAME,
)
from gengallery.services.scaffold_assets import (
    ScaffoldPackagingError,
    ScaffoldTargetExistsError,
    iter_scaffold_files,
    materialize_scaffold,
)


def test_iter_scaffold_files_includes_config_templates_and_example_gallery() -> None:
    paths = {rel for rel, _ in iter_scaffold_files()}
    assert CONFIG_FILENAME in paths
    assert f"{GALLERIES_DIRNAME}/{SCAFFOLD_EXAMPLE_GALLERY_DIRNAME}/gallery.yaml" in paths
    assert f"{TEMPLATES_DIRNAME}/index.html.jinja" in paths
    assert f"{TEMPLATES_DIRNAME}/tailwind/tailwind.config.js" in paths


def test_materialize_scaffold_writes_expected_tree(tmp_path: Path) -> None:
    materialize_scaffold(tmp_path)
    assert (tmp_path / CONFIG_FILENAME).is_file()
    assert (tmp_path / TEMPLATES_DIRNAME / "index.html.jinja").is_file()
    gal_root = tmp_path / GALLERIES_DIRNAME / SCAFFOLD_EXAMPLE_GALLERY_DIRNAME
    assert (gal_root / "gallery.yaml").is_file()


def test_materialize_scaffold_refuses_overwrite_by_default(tmp_path: Path) -> None:
    materialize_scaffold(tmp_path)
    with pytest.raises(ScaffoldTargetExistsError):
        materialize_scaffold(tmp_path)


def test_materialize_scaffold_overwrite_true_replaces(tmp_path: Path) -> None:
    materialize_scaffold(tmp_path)
    materialize_scaffold(tmp_path, overwrite=True)
    assert (tmp_path / CONFIG_FILENAME).is_file()


def test_materialize_scaffold_empty_target_no_partial_write_on_conflict(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILENAME).write_text("keep\n", encoding="utf-8")
    with pytest.raises(ScaffoldTargetExistsError):
        materialize_scaffold(tmp_path)
    assert (tmp_path / CONFIG_FILENAME).read_text(encoding="utf-8") == "keep\n"
    assert not (tmp_path / TEMPLATES_DIRNAME).exists()


def test_read_bytes_failure_surfaces_as_packaging_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from gengallery.services import scaffold_assets as sa

    class BadTraversable:
        name = "x"

        def is_dir(self) -> bool:
            return False

        def is_file(self) -> bool:
            return True

        def read_bytes(self) -> bytes:
            raise OSError("simulated read failure")

    def fake_iter() -> list[tuple[str, object]]:
        return [("only_file.txt", BadTraversable())]

    monkeypatch.setattr(sa, "iter_scaffold_files", fake_iter)
    with pytest.raises(ScaffoldPackagingError, match="failed to read packaged resource"):
        materialize_scaffold(tmp_path)
