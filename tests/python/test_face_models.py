"""Tests for face model cache path resolution."""

from __future__ import annotations

from gengallery.constants import ENV_XDG_CACHE_HOME, FACE_MODELS_SUBDIR, XDG_CACHE_APP_DIRNAME
from gengallery.services.face_models import face_model_cache_root, xdg_cache_home


def test_xdg_cache_home_default(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(ENV_XDG_CACHE_HOME, raising=False)
    monkeypatch.setattr("gengallery.services.face_models.Path.home", lambda: tmp_path)

    assert xdg_cache_home() == tmp_path / ".cache"


def test_xdg_cache_home_respects_env(monkeypatch, tmp_path) -> None:
    custom = tmp_path / "custom-cache"
    monkeypatch.setenv(ENV_XDG_CACHE_HOME, str(custom))

    assert xdg_cache_home() == custom


def test_face_model_cache_root_under_xdg_cache(monkeypatch, tmp_path) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv(ENV_XDG_CACHE_HOME, str(cache))

    root = face_model_cache_root()
    assert root == cache / XDG_CACHE_APP_DIRNAME
    assert (root / FACE_MODELS_SUBDIR).as_posix().endswith(
        f"{XDG_CACHE_APP_DIRNAME}/{FACE_MODELS_SUBDIR}"
    )
