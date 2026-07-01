"""URL path helpers for configurable ``base_path`` support."""

from __future__ import annotations


def normalize_base_path(raw: str | None) -> str:
    """Return a canonical URL prefix, or ``""`` when no prefix applies.

    Strips trailing slashes and treats root-only values (``"/"``, ``"/gallery/"``)
    as their non-trailing form.  An empty or ``"/"`` prefix means no prefix.
    """
    stripped = (raw or "").rstrip("/")
    if not stripped or stripped == "/":
        return ""
    return stripped


def base_path_from_config(config: dict | None) -> str:
    """Read and normalize ``base_path`` from a project config mapping."""
    if not config:
        return ""
    return normalize_base_path(config.get("base_path"))


def url(path: str, base_path: str = "") -> str:
    """Prepend *base_path* to a root-relative *path*.

    The *path* is returned unchanged when *base_path* is empty, *path* is already
    prefixed, or *path* is an absolute URL (``http://``, ``https://``, ``data:``,
    ``#``) or protocol-relative (``//…``).
    """
    prefix = normalize_base_path(base_path)
    if not prefix:
        return path
    if path.startswith(("http://", "https://", "data:", "#", "//")):
        return path
    if path == prefix or path.startswith(prefix + "/"):
        return path
    if path.startswith("/"):
        return f"{prefix}{path}"
    return f"{prefix}/{path}"


def translate_request_path(path: str, base_path: str) -> str:
    """Strip *base_path* from an incoming HTTP request path for static serving."""
    prefix = normalize_base_path(base_path)
    if prefix and path.startswith(prefix + "/"):
        return path[len(prefix) :]
    if prefix and path == prefix:
        return "/"
    return path
