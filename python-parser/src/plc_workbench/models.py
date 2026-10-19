"""Versioned private source records, separate from sanitized publication reports.

IDs identify evidence inside one byte snapshot. They are not persistent equipment
or review-decision IDs and must not be reused across changed source snapshots.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSnapshot:
    id: str
    sha256: str
    size_bytes: int
    data: bytes = field(repr=False)


@dataclass(frozen=True)
class EntityRecord:
    id: str
    kind: str
    name: str | None
    locator: str
    parent_id: str | None
    scope_id: str | None
    attributes: dict[str, str] = field(repr=False)
    description: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class InstructionRecord:
    id: str
    opcode: str
    arguments: tuple[str, ...] = field(repr=False)
    start: int
    end: int
    semantic_status: str = "not_analyzed"


@dataclass(frozen=True)
class RungRecord:
    id: str
    locator: str
    parent_id: str | None
    scope_id: str | None
    ordinal: int
    number: str | None
    type: str | None
    text: str | None = field(repr=False)
    comment: str | None = field(repr=False)
    parse_status: str
    metrics: dict[str, int]
    instructions: list[InstructionRecord]
    structure: dict[str, Any] | None


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    source_id: str | None
    locator: str
    message: str


@dataclass(frozen=True)
class InventoryResult:
    snapshot: dict[str, str | int]
    export_attributes: dict[str, str]
    entities: list[EntityRecord]
    rungs: list[RungRecord]
    diagnostics: list[Diagnostic]
    counts: dict[str, int]
    routine_types: dict[str, int]
    instruction_counts: dict[str, int]
    coverage: dict[str, Any]
    status: str
    schema_version: int = 3
    parser_version: str = "source-inventory-3"
    analysis_scope: str = "source_structure_only"
    semantic_analysis: str = "not_implemented"

    def to_dict(self) -> dict[str, Any]:
        """Return private JSON-ready records; this is not a scrubbed export."""
        return asdict(self)
