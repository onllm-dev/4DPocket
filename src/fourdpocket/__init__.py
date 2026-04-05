"""4DPocket - Self-hosted AI-powered personal knowledge base."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fourdpocket")
except PackageNotFoundError:
    __version__ = "0.1.0"
