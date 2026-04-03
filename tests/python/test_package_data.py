"""Packaged assets discoverable via importlib.resources (wheel/sdist parity)."""

from __future__ import annotations

from importlib.resources import files

from gengallery.constants import CONFIG_FILENAME, TEMPLATES_DIRNAME
from gengallery.services.scaffold_assets import SCAFFOLD_SUBDIR


def test_gengallery_assets_contains_scaffold_config() -> None:
    root = files("gengallery.assets")
    assert root.is_dir()
    config = root.joinpath(SCAFFOLD_SUBDIR).joinpath(CONFIG_FILENAME)
    assert config.is_file(), "scaffold config must ship in package data"


def test_gengallery_assets_contains_template_marker() -> None:
    root = files("gengallery.assets")
    marker = root.joinpath(TEMPLATES_DIRNAME).joinpath("index.html.jinja")
    assert marker.is_file(), "Jinja templates must ship in package data"
