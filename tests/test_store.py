from concurrent.futures import ThreadPoolExecutor

import pytest

from compactionlab.schemas import ContextRequest, Event, MemoryRecord, WriteBatch
from compactionlab.store import RevisionConflict, Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "memory.sqlite3")


def record(identifier="old", text="Old shipping threshold is 5000", **kwargs):
    return MemoryRecord(id=identifier, kind="fact", text=text, source_ids=["source"], **kwargs)


def seed(store, namespace="project"):
    store.write(
        namespace,
        WriteBatch(
            expected_revision=0,
            events=[Event(id="source", source="user", text="Shipping facts")],
            records=[record()],
        ),
    )


def test_supersession_preserves_history_and_current_context(store):
    seed(store)
    store.write(
        "project",
        WriteBatch(
            expected_revision=1,
            records=[record("new", "Current shipping threshold is 7500", supersedes=["old"])],
        ),
    )
    snapshot = store.snapshot("project")
    assert [r["effective_state"] for r in snapshot["records"]] == ["superseded", "active"]
    context = store.context("project", ContextRequest(query="shipping threshold"))
    assert context["record_ids"] == ["new"]
    assert "Shipping facts" in context["text"]
    assert "5000" not in context["text"]
    plain = store.context("project", ContextRequest(query="shipping threshold", mode="plain"))
    assert set(plain["record_ids"]) == {"old", "new"}


def test_write_conflict_is_atomic(store):
    seed(store)
    with pytest.raises(RevisionConflict):
        store.write("project", WriteBatch(expected_revision=0, records=[record("new")]))
    assert len(store.snapshot("project")["records"]) == 1


@pytest.mark.parametrize(
    "invalid",
    [
        MemoryRecord(id="new", kind="fact", text="bad", source_ids=["unknown"]),
        record("new", depends_on=["missing"]),
        record("new", supersedes=["new"]),
        record("old"),
    ],
)
def test_invalid_reference_or_rewrite_rolls_back(store, invalid):
    seed(store)
    with pytest.raises(ValueError):
        store.write(
            "project",
            WriteBatch(
                expected_revision=1,
                records=[invalid],
                events=[
                    Event(id="another", source="tool", text="Must roll back with invalid records")
                ],
            ),
        )
    assert store.snapshot("project")["revision"] == 1
    assert len(store.snapshot("project")["events"]) == 1


def test_dependency_closure_is_included_as_a_unit(store):
    seed(store)
    store.write(
        "project",
        WriteBatch(
            expected_revision=1,
            records=[record("verify", "authentication needs testing", depends_on=["old"])],
        ),
    )
    context = store.context("project", ContextRequest(query="authentication"))
    assert context["record_ids"] == ["verify", "old"]
    tight = store.context("project", ContextRequest(query="authentication", byte_budget=256))
    assert tight["bytes"] <= 256
    assert "verify" not in tight["record_ids"]


def test_cycles_in_batch_are_rejected(store):
    seed(store)
    with pytest.raises(ValueError, match="acyclic"):
        store.write(
            "project",
            WriteBatch(
                expected_revision=1,
                records=[record("a", depends_on=["b"]), record("b", depends_on=["a"])],
            ),
        )


def test_utf8_budget_never_splits_records(store):
    store.write(
        "project",
        WriteBatch(
            expected_revision=0,
            events=[Event(id="source", source="user", text="Unicode source")],
            records=[record(text="東京 " * 200)],
        ),
    )
    context = store.context("project", ContextRequest(query="東京", byte_budget=256))
    assert context["text"] == "[]"
    assert context["bytes"] == 2


def test_scope_isolation_including_ranking(store):
    seed(store, "one")
    before = store.context("one", ContextRequest(query="shipping"))
    seed(store, "two")
    store.write(
        "two",
        WriteBatch(expected_revision=1, records=[record("secret", "Private shipping supplier")]),
    )
    assert store.context("one", ContextRequest(query="shipping")) == before
    assert "Private" not in before["text"]


def test_two_concurrent_writers_cannot_overwrite_each_other(store):
    seed(store)

    def write(identifier):
        try:
            store.write("project", WriteBatch(expected_revision=1, records=[record(identifier)]))
            return "ok"
        except RevisionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, ["a", "b"])) == ["conflict", "ok"]
    assert store.snapshot("project")["revision"] == 2


@pytest.mark.parametrize("namespace", ["../escape", "", "x" * 101, "name with spaces"])
def test_invalid_namespace_rejected(store, namespace):
    with pytest.raises(ValueError):
        store.write(namespace, WriteBatch(expected_revision=0))
