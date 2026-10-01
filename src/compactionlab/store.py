"""Append-only SQLite records with atomic, version-checked writes and FTS retrieval."""

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from compactionlab.packets import compact_packet
from compactionlab.schemas import ContextRequest, WriteBatch


class RevisionConflict(ValueError):
    pass


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS namespaces (
                  name TEXT PRIMARY KEY, revision INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS events (
                  namespace TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                  seq INTEGER NOT NULL, PRIMARY KEY(namespace, id));
                CREATE TABLE IF NOT EXISTS records (
                  namespace TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                  seq INTEGER NOT NULL, PRIMARY KEY(namespace, id));
                CREATE VIRTUAL TABLE IF NOT EXISTS record_search USING fts5(
                  namespace UNINDEXED, id UNINDEXED, text, tokenize='unicode61');
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def validate_namespace(name: str):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", name):
            raise ValueError(
                "Namespace must be 1–100 letters, numbers, dots, dashes or underscores"
            )

    def write(self, namespace: str, batch: WriteBatch) -> int:
        self.validate_namespace(namespace)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO namespaces(name) VALUES (?)", (namespace,))
            revision = db.execute(
                "SELECT revision FROM namespaces WHERE name=?", (namespace,)
            ).fetchone()[0]
            if revision != batch.expected_revision:
                raise RevisionConflict(
                    f"Expected revision {batch.expected_revision}, got {revision}"
                )
            events = {
                row["id"]
                for row in db.execute("SELECT id FROM events WHERE namespace=?", (namespace,))
            }
            records = {
                row["id"]: json.loads(row["body"])
                for row in db.execute("SELECT id,body FROM records WHERE namespace=?", (namespace,))
            }
            event_ids = [event.id for event in batch.events]
            record_ids = [record.id for record in batch.records]
            if len(set(event_ids)) != len(event_ids) or set(event_ids) & events:
                raise ValueError("Event IDs are immutable and must be unique within the namespace")
            if len(set(record_ids)) != len(record_ids) or set(record_ids) & records.keys():
                raise ValueError("Record IDs are immutable and must be unique within the namespace")
            events.update(event_ids)
            records.update({record.id: record.model_dump() for record in batch.records})
            for record in batch.records:
                if not set(record.source_ids) <= events:
                    raise ValueError(f"Unknown source for record {record.id}")
                refs = set(record.supersedes + record.depends_on)
                if record.id in refs or not refs <= records.keys():
                    raise ValueError(f"Unknown or self-referential link in record {record.id}")
            self._check_cycles(records)
            event_seq = db.execute(
                "SELECT COALESCE(MAX(seq),0) FROM events WHERE namespace=?", (namespace,)
            ).fetchone()[0]
            for offset, event in enumerate(batch.events, start=1):
                db.execute(
                    "INSERT INTO events VALUES (?,?,?,?)",
                    (namespace, event.id, event.model_dump_json(), event_seq + offset),
                )
            record_seq = db.execute(
                "SELECT COALESCE(MAX(seq),0) FROM records WHERE namespace=?", (namespace,)
            ).fetchone()[0]
            for offset, record in enumerate(batch.records, start=1):
                db.execute(
                    "INSERT INTO records VALUES (?,?,?,?)",
                    (namespace, record.id, record.model_dump_json(), record_seq + offset),
                )
                db.execute(
                    "INSERT INTO record_search(namespace,id,text) VALUES (?,?,?)",
                    (namespace, record.id, f"{record.entity} {record.kind} {record.text}"),
                )
            db.execute("UPDATE namespaces SET revision=revision+1 WHERE name=?", (namespace,))
            return revision + 1

    @staticmethod
    def _check_cycles(records: dict):
        visited, visiting = set(), set()

        def visit(identifier):
            if identifier in visiting:
                raise ValueError("Record relationships must be acyclic")
            if identifier in visited:
                return
            visiting.add(identifier)
            for related in records[identifier]["depends_on"] + records[identifier]["supersedes"]:
                visit(related)
            visiting.remove(identifier)
            visited.add(identifier)

        for identifier in records:
            visit(identifier)

    def snapshot(self, namespace: str) -> dict:
        self.validate_namespace(namespace)
        with self.connect() as db:
            db.execute("BEGIN")
            row = db.execute(
                "SELECT revision FROM namespaces WHERE name=?", (namespace,)
            ).fetchone()
            if row is None:
                raise KeyError(namespace)
            records = [
                dict(json.loads(r["body"]), seq=r["seq"])
                for r in db.execute(
                    "SELECT body,seq FROM records WHERE namespace=? ORDER BY seq", (namespace,)
                )
            ]
            events = [
                json.loads(r["body"])
                for r in db.execute(
                    "SELECT body FROM events WHERE namespace=? ORDER BY seq", (namespace,)
                )
            ]
        superseded = {identifier for record in records for identifier in record["supersedes"]}
        for record in records:
            record["effective_state"] = (
                "superseded" if record["id"] in superseded else record["state"]
            )
        return {"namespace": namespace, "revision": row[0], "events": events, "records": records}

    def namespaces(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM namespaces ORDER BY name")]

    def context(
        self, namespace: str, request: ContextRequest, *, token_budget=None, counter=None
    ) -> dict:
        if token_budget is not None and counter is None:
            raise ValueError("Token-bounded retrieval requires a calibrated counter")
        snapshot = self.snapshot(namespace)
        records = snapshot["records"]
        by_id = {record["id"]: record for record in records}
        terms = list(dict.fromkeys(re.findall(r"\w+", request.query.lower())))[:40]
        ranks = {}
        if terms:
            expression = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
            with self.connect() as db:
                matches = db.execute(
                    "SELECT id FROM record_search "
                    "WHERE record_search MATCH ? AND namespace=? ORDER BY id",
                    (expression, namespace),
                )
                # Score within the namespace; unrelated projects must not alter IDF/ranking.
                candidates = {row["id"] for row in matches}
                ranks = {
                    record["id"]: -len(
                        set(terms)
                        & set(
                            re.findall(
                                r"\w+",
                                f"{record['entity']} {record['kind']} {record['text']}".lower(),
                            )
                        )
                    )
                    for record in records
                    if record["id"] in candidates
                }
        records = sorted(records, key=lambda r: (ranks.get(r["id"], 1), -r["seq"], r["id"]))
        if request.mode in {"structured", "compact"}:
            records = [r for r in records if r["effective_state"] != "superseded"]
        units, included = [], set()
        for record in records:
            group = [record]
            if request.mode in {"structured", "compact"}:
                queue = list(record["depends_on"])
                while queue:
                    dependency = by_id[queue.pop(0)]
                    if dependency["id"] not in {r["id"] for r in group}:
                        group.append(dependency)
                        queue.extend(dependency["depends_on"])
                rendered = []
                for item in group:
                    value = {k: v for k, v in item.items() if k != "seq"}
                    value["sources"] = [
                        event for event in snapshot["events"] if event["id"] in item["source_ids"]
                    ]
                    rendered.append(value)
            else:
                rendered = [{"id": record["id"], "kind": record["kind"], "text": record["text"]}]
            additions = [unit for unit in rendered if unit["id"] not in included]
            candidate = units + additions
            encoded = (
                compact_packet(candidate, snapshot["events"])
                if request.mode == "compact"
                else json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
            )
            fits = (
                counter.history_tokens(encoded) <= token_budget
                if token_budget is not None
                else len(encoded.encode()) <= request.byte_budget
            )
            if fits:
                units = candidate
                included.update(unit["id"] for unit in additions)
        text = (
            compact_packet(units, snapshot["events"])
            if request.mode == "compact"
            else json.dumps(units, ensure_ascii=False, separators=(",", ":"))
        )
        return {
            "namespace": namespace,
            "revision": snapshot["revision"],
            "mode": request.mode,
            "text": text,
            "bytes": len(text.encode()),
            "byte_budget": request.byte_budget if token_budget is None else None,
            "token_budget": token_budget,
            "historical_tokens": counter.history_tokens(text) if counter else None,
            "record_ids": [unit["id"] for unit in units],
            "omitted_records": len(by_id.keys() - included),
        }
