"""Compatibility shim to expose the ``src.lost_hiker`` package at top level."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

_src_pkg: ModuleType = import_module("src.lost_hiker")

__all__ = getattr(_src_pkg, "__all__", [])  # type: ignore[assignment]
__path__ = _src_pkg.__path__  # type: ignore[attr-defined]
__file__ = getattr(_src_pkg, "__file__", __file__)  # type: ignore[name-defined]


def __getattr__(name: str):
    return getattr(_src_pkg, name)


def __dir__() -> list[str]:
    return sorted(set(dir(_src_pkg)))
