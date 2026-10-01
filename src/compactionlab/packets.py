"""Lossless sparse records with a shared, chronological source table.

Empty strings and lists carry no additional information. State and effective_state
remain explicit, including superseded dependencies. No source text is shortened.
"""

import json

from compactionlab.schemas import MemoryRecord


def compact_packet(units: list[dict], events: list[dict]) -> str:
    if not units:
        return "[]"
    source_ids = {event["id"] for unit in units for event in unit["sources"]}
    records = [
        {key: value for key, value in unit.items() if key != "sources" and value not in ("", [])}
        for unit in units
    ]
    return json.dumps(
        {"records": records, "sources": [event for event in events if event["id"] in source_ids]},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def expand_packet(text: str) -> list[dict]:
    """Reconstruct the verbose representation for fidelity checks, without an LLM."""
    packet = json.loads(text)
    if packet == []:
        return []
    units = []
    for sparse in packet["records"]:
        fields = {key: value for key, value in sparse.items() if key != "effective_state"}
        record = MemoryRecord.model_validate(fields).model_dump()
        record["effective_state"] = sparse["effective_state"]
        record["sources"] = [
            event for event in packet["sources"] if event["id"] in record["source_ids"]
        ]
        units.append(record)
    return units
