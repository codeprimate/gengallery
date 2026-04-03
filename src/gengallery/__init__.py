"""Installable gallery build and deploy CLI package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("gengallery")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
