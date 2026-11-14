"""One adapter per agent tool; see `base.py` for what an adapter provides.

Adding a tool means adding a module here with a module-level `ADAPTER` and its
name in `TOOLS`; nothing outside this package changes.
"""

from __future__ import annotations

from importlib import import_module

from .base import Adapter

TOOLS = ("claude",)
DEFAULT = "claude"


def get(name: str = DEFAULT) -> Adapter:
    if name not in TOOLS:
        raise ValueError(f"unknown tool {name!r}; known: {', '.join(TOOLS)}")
    return import_module(f"{__name__}.{name}").ADAPTER
