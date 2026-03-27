"""DAMPF - Data Aggregation and Modular Processing Framework (package root)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dampf")
except PackageNotFoundError:
    __version__ = "0.1.0"
