"""
Provenance helpers: translate ORM lineage rows into chat-safe citation objects.

Every numeric or factual chat answer should cite at least one `Provenance` row
so agents never fabricate numbers without traceability.
"""

from __future__ import annotations

from collections.abc import Iterable

from db.models import Provenance
from db.schema import Citation


def provenance_rows_to_citations(rows: Iterable[Provenance]) -> list[Citation]:
    """Convert SQLAlchemy provenance rows into API citations."""
    out: list[Citation] = []
    for r in rows:
        out.append(
            Citation(
                internal_entity_id=r.internal_entity_id,
                source_system=r.source_system,
                source_field=r.source_field,
                source_row_id=r.source_row_id,
                field_name=r.field_name,
            )
        )
    return out


def merge_citations_unique(citations: list[Citation]) -> list[Citation]:
    """De-duplicate citations that point to the same source cell."""
    seen: set[tuple[str, str, str, str]] = set()
    merged: list[Citation] = []
    for c in citations:
        key = (c.internal_entity_id, c.source_system, c.source_field, c.source_row_id)
        if key in seen:
            continue
        seen.add(key)
        merged.append(c)
    return merged
