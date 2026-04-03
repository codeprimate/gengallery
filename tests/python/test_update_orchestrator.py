"""Tests for update pipeline orchestration (stage order and wiring)."""

from __future__ import annotations

from pathlib import Path

from gengallery.services.update import run_update


def test_run_update_invokes_stages_in_order(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        "gengallery.services.update.image_processor.main",
        lambda: calls.append("image"),
    )
    monkeypatch.setattr(
        "gengallery.services.update.video_processor.main",
        lambda: calls.append("video"),
    )
    monkeypatch.setattr(
        "gengallery.services.update.gallery_processor.main",
        lambda: calls.append("gallery"),
    )
    monkeypatch.setattr(
        "gengallery.services.update.generator.main",
        lambda: calls.append("generator"),
    )

    cfg = {"source_path": "./galleries", "output_path": "./export"}
    run_update(tmp_path, cfg)

    assert calls == ["image", "video", "gallery", "generator"]


def test_apply_runtime_config_populates_shared_config(tmp_path: Path, monkeypatch) -> None:
    """Smoke: shared config dict is filled before stages (video reads image_processor.config)."""
    monkeypatch.setattr("gengallery.services.update.image_processor.main", lambda: None)
    monkeypatch.setattr("gengallery.services.update.video_processor.main", lambda: None)
    monkeypatch.setattr("gengallery.services.update.gallery_processor.main", lambda: None)
    monkeypatch.setattr("gengallery.services.update.generator.main", lambda: None)

    from gengallery.services import image_processor as ip

    cfg = {"source_path": "s", "output_path": "o", "site_name": "t"}
    run_update(tmp_path, cfg)
    assert ip.config.get("site_name") == "t"
    assert ip.config.get("source_path") == "s"
