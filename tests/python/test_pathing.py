"""Tests for path normalization and config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from gengallery.constants import CONFIG_FILENAME
from gengallery.errors import CliUserError
from gengallery.pathing import (
    load_project_config,
    normalize_cli_project_path,
    project_config_path,
)
from gengallery.validation import (
    validate_existing_project_for_update,
    validate_serve_artifacts,
    validate_ssh_config,
)


def test_normalize_omitted_path_is_cwd(tmp_path: Path):
    assert normalize_cli_project_path(None, tmp_path) == tmp_path.resolve()


def test_normalize_relative_path_from_cwd(tmp_path: Path):
    sub = tmp_path / "gallery"
    sub.mkdir()
    assert normalize_cli_project_path("gallery", tmp_path) == sub.resolve()


def test_normalize_absolute_path(tmp_path: Path):
    sub = tmp_path / "absproj"
    sub.mkdir()
    assert normalize_cli_project_path(str(sub), tmp_path) == sub.resolve()


def test_project_config_path():
    root = Path("/tmp/proj")
    assert project_config_path(root) == Path("/tmp/proj") / CONFIG_FILENAME


def test_load_project_config_missing(tmp_path: Path):
    with pytest.raises(CliUserError, match="not found"):
        load_project_config(tmp_path)


def test_load_project_config_empty(tmp_path: Path):
    cfg = tmp_path / CONFIG_FILENAME
    cfg.write_text("   \n", encoding="utf-8")
    with pytest.raises(CliUserError, match="empty"):
        load_project_config(tmp_path)


def test_load_project_config_invalid_yaml(tmp_path: Path):
    cfg = tmp_path / CONFIG_FILENAME
    cfg.write_text("{not: valid", encoding="utf-8")
    with pytest.raises(CliUserError, match="Invalid YAML"):
        load_project_config(tmp_path)


def test_load_project_config_not_mapping(tmp_path: Path):
    cfg = tmp_path / CONFIG_FILENAME
    cfg.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(CliUserError, match="mapping"):
        load_project_config(tmp_path)


def test_load_project_config_ok(tmp_path: Path):
    cfg = tmp_path / CONFIG_FILENAME
    cfg.write_text("site_name: x\n", encoding="utf-8")
    data = load_project_config(tmp_path)
    assert data == {"site_name": "x"}


def test_validate_existing_project_requires_source_dir(tmp_path: Path):
    cfg = tmp_path / CONFIG_FILENAME
    cfg.write_text(
        "source_path: ./galleries\noutput_path: ./export\n",
        encoding="utf-8",
    )
    with pytest.raises(CliUserError, match="Source gallery directory"):
        validate_existing_project_for_update(tmp_path)


def test_validate_existing_project_ok(tmp_path: Path):
    gal = tmp_path / "galleries"
    gal.mkdir()
    cfg = tmp_path / CONFIG_FILENAME
    cfg.write_text(
        "source_path: ./galleries\noutput_path: ./export\n",
        encoding="utf-8",
    )
    out = validate_existing_project_for_update(tmp_path)
    assert out["source_path"] == "./galleries"


def test_validate_serve_artifacts_requires_public_html(tmp_path: Path):
    cfg = tmp_path / CONFIG_FILENAME
    cfg.write_text("output_path: ./export\n", encoding="utf-8")
    (tmp_path / "export").mkdir()
    with pytest.raises(CliUserError, match="gengallery update"):
        validate_serve_artifacts(tmp_path, {"output_path": "./export"})


def test_validate_serve_artifacts_ok(tmp_path: Path):
    pub = tmp_path / "export" / "public_html"
    pub.mkdir(parents=True)
    site = validate_serve_artifacts(
        tmp_path,
        {"output_path": "./export"},
    )
    assert site == pub.resolve()


def test_validate_ssh_requires_post_sync_commands():
    with pytest.raises(CliUserError, match="post_sync_commands"):
        validate_ssh_config({"ssh": {}})


def test_validate_ssh_merges_defaults():
    merged = validate_ssh_config(
        {
            "ssh": {
                "post_sync_commands": ["echo ok"],
            },
        },
    )
    assert merged["post_sync_commands"] == ["echo ok"]
    assert merged["user"] == "admin"
    assert merged["host"] == "gallery.nil42.com"
