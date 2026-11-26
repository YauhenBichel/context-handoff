"""What the rest of the package needs from an agent tool.

Two small interfaces, so a caller depends only on what it uses: the report only
reads sessions; the hook handlers read sessions and also build hook replies.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from ..usage import Session


class SessionReader(Protocol):
    name: str

    def read(self, path: str | Path) -> Session:
        """The main-thread model replies of one session file, in order."""

    def session_files(self, root: Path | None = None) -> Iterator[tuple[str, Path]]:
        """(project, session file) for every session file under `root` (default: the tool's own)."""


class HookReplies(Protocol):
    agent: str  # who writes the note, as named in messages to the owner
    clear_command: str  # what the owner types to start fresh

    def notice(self, event: str, line: str, context: str = "", **extra) -> dict:
        """A reply that shows `line` to the owner and adds `context` for the agent.

        With an empty `line` nothing is shown: the reply only adds `context`.
        """

    def block(self, reason: str) -> dict:
        """A reply that stops the prompt and shows `reason`."""


class Adapter(SessionReader, HookReplies, Protocol):
    """Everything one tool provides."""
