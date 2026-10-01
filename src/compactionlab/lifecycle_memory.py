"""Generic typed-event retrieval; no fixture IDs, expected values, or grade annotations."""

import json
import re

from compactionlab.lifecycle_types import LedgerEvent
from compactionlab.schemas import Event, MemoryRecord, WriteBatch


def encode(entries):
    return json.dumps([row.packet() for row in entries], ensure_ascii=False, separators=(",", ":"))


def current_heads(entries):
    heads = {}
    for entry in entries:
        if entry.source in {"user", "tool"} and entry.kind != "claim":
            heads[entry.entity] = entry
    return heads


def seed_memory(store, namespace, entries):
    heads, records = {}, []
    kinds = {
        "goal": "decision",
        "constraint": "requirement",
        "task": "task",
        "note": "artifact",
        "claim": "fact",
    }
    for entry in entries:
        records.append(
            MemoryRecord(
                id=entry.id,
                kind=kinds[entry.kind],
                text=json.dumps(entry.packet(), ensure_ascii=False, separators=(",", ":")),
                source_ids=[entry.id],
                entity=entry.entity,
                applies_to=entry.revision,
                state="completed"
                if entry.state == "completed"
                else "uncertain"
                if entry.state == "canceled" or entry.source == "assistant"
                else "active",
                supersedes=entry.replaces,
                depends_on=[heads[name].id for name in entry.requires],
            )
        )
        if entry.source in {"user", "tool"} and entry.kind != "claim":
            heads[entry.entity] = entry
    store.write(
        namespace,
        WriteBatch(
            expected_revision=0,
            events=[
                Event(
                    id=e.id,
                    source=e.source,
                    text=json.dumps(e.packet(), ensure_ascii=False, separators=(",", ":")),
                )
                for e in entries
            ],
            records=records,
        ),
    )


def load_memory(store, namespace):
    return [
        LedgerEvent.model_validate_json(record["text"])
        for record in store.snapshot(namespace)["records"]
    ]


def retrieve(entries, query, budget, counter, policy):
    """Equal encoding and allowance; links resolve entity heads within the same revision."""
    terms = set(re.findall(r"\w+", query.lower()))
    positions = {row.id: i for i, row in enumerate(entries)}
    heads = current_heads(entries)

    def lexical(row):
        words = set(re.findall(r"\w+", f"{row.entity} {row.kind} {row.text}".lower()))
        return (-len(terms & words), -positions[row.id], row.id)

    if policy == "recent_history":
        roots = list(reversed(entries))
    elif policy == "lexical":
        roots = sorted(entries, key=lexical)
    elif policy in {"current_no_links", "linked_current"}:

        def priority(row):
            kind = (
                0
                if row.kind == "task" and row.state == "pending"
                else 1
                if row.kind == "task"
                else 2
                if row.kind == "constraint"
                else 3
                if row.kind == "goal"
                else 4
            )
            return (kind, *lexical(row))

        roots = sorted(heads.values(), key=priority)
    else:
        raise ValueError("Unknown lifecycle policy")
    selected = {}
    for root in roots:
        group = {root.id: root}
        if policy == "linked_current":
            queue = [root]
            while queue:
                row = queue.pop(0)
                for entity in row.requires:
                    parent = heads.get(entity)
                    if parent is None or (parent.revision and parent.revision != row.revision):
                        raise ValueError("Dependency is missing or belongs to another revision")
                    if parent.id not in group:
                        group[parent.id] = parent
                        queue.append(parent)
        candidate = {**selected, **group}
        ordered = sorted(candidate.values(), key=lambda row: positions[row.id])
        if counter.history_tokens(encode(ordered)) <= budget:
            selected = candidate
        elif policy == "recent_history":
            break  # A contiguous suffix, never skip a large recent event to admit older data.
    ordered = sorted(selected.values(), key=lambda row: positions[row.id])
    return {"context": encode(ordered), "record_ids": [row.id for row in ordered]}
