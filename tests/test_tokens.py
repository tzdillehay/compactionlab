import json

import pytest

from compactionlab.schemas import ContextRequest, MemoryRecord, WriteBatch
from compactionlab.store import Store
from compactionlab.tokens import cache_folder, load_counter


def test_tokenizer_hash_runtime_and_template_changes_fail_closed(prepared_counter, tmp_path):
    runtime = prepared_counter.manifest["runtime"]
    assert load_counter(tmp_path, "qwen3:8b", runtime).count("SMS") > 0
    with pytest.raises(ValueError, match="changed"):
        load_counter(tmp_path, "qwen3:8b", dict(runtime, digest="different"))
    path = cache_folder(tmp_path, "qwen3:8b") / "tokenizer.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="integrity"):
        load_counter(tmp_path, "qwen3:8b", runtime)


def test_escaped_history_is_the_bounded_unit(prepared_counter):
    text = '{"text":"Café 東京\nRevision B"}'
    assert prepared_counter.history_tokens(text) == prepared_counter.count(
        json.dumps(text, ensure_ascii=False)
    )
    assert prepared_counter.history_tokens(text) > prepared_counter.count(text)


def test_token_limits_keep_atomic_dependency_groups(prepared_counter, tmp_path):
    from compactionlab.schemas import Event

    store = Store(tmp_path / "db")
    store.write(
        "demo",
        WriteBatch(
            expected_revision=0,
            events=[Event(id="e", source="user", text="Café 東京")],
            records=[
                MemoryRecord(id="base", kind="fact", text="SMS", source_ids=["e"]),
                MemoryRecord(
                    id="replacement",
                    kind="requirement",
                    text="Revision B",
                    source_ids=["e"],
                    depends_on=["base"],
                ),
            ],
        ),
    )
    query = ContextRequest(query="Revision", mode="structured")
    full = store.context("demo", query, token_budget=10000, counter=prepared_counter)
    assert set(full["record_ids"]) == {"base", "replacement"}
    small = store.context(
        "demo", query, token_budget=full["historical_tokens"] - 1, counter=prepared_counter
    )
    assert "replacement" not in small["record_ids"]
    assert small["historical_tokens"] <= small["token_budget"]
    assert small["byte_budget"] is None
    with pytest.raises(ValueError, match="calibrated"):
        store.context("demo", query, token_budget=100)
