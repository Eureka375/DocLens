from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class Span:
    """Half-open Unicode code-point offsets in a snapshot's display text."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str
    span: Span
    location: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    path: Path
    sha256: str
    text: str
    blocks: tuple[TextBlock, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Change:
    kind: Literal["insert", "delete", "replace", "move", "move_replace"]
    left: Span
    right: Span
    left_location: str
    right_location: str
    left_edits: tuple[Span, ...]
    right_edits: tuple[Span, ...]


@dataclass(frozen=True, slots=True)
class Comparison:
    changes: tuple[Change, ...]
    used_coarse_matching: bool
