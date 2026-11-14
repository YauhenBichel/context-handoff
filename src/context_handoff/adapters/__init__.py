"""One module per agent tool: how to read its session files.

Each adapter module has:

  NAME                 the tool name used with `--tool`
  read(path) -> usage.Session
                       the main-thread model replies of one session file, in order
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

TOOLS = ("claude",)
DEFAULT = "claude"


def get(name: str = DEFAULT) -> ModuleType:
    if name not in TOOLS:
        raise ValueError(f"unknown tool {name!r}; known: {', '.join(TOOLS)}")
    return import_module(f"{__name__}.{name}")
