import json
from pathlib import Path

import pytest
from filelock import FileLock

from compactionlab.experiment import READER_SYSTEM
from compactionlab.fixtures import load_case
from compactionlab.ollama import ModelFailure
from compactionlab.packets import compact_packet, expand_packet
from compactionlab.representation import load_frozen, packets, run_representation, seed_graph
from compactionlab.schemas import ContextRequest, Continuation, RepresentationRequest
from compactionlab.store import Store

SOURCE = Path(__file__).resolve().parents[1] / "results/token-budget-2026-10-01/1b62ebbc316d.json"


def test_shared_source_codec_preserves_unicode_states_order_and_links(tmp_path):
    store = Store(tmp_path / "db")
    for row in load_frozen(SOURCE)["cases"]:
        seed_graph(store, row["case"], row)
        result = store.context(row["case"], ContextRequest(query="current", byte_budget=32000))
        units = json.loads(result["text"])
        # Include repeated source references and non-default metadata explicitly.
        units[0]["text"] += " Café 東京"
        units[0]["entity"] = "current_entity"
        units[0]["applies_to"] = "revision-B"
        units[0]["state"] = "completed"
        units[0]["sources"] += units[-1]["sources"]
        units[0]["source_ids"] += [e["id"] for e in units[-1]["sources"]]
        events = store.snapshot(row["case"])["events"]
        # Restore chronological sources before encoding, as the actual Store does.
        units[0]["sources"] = [e for e in events if e["id"] in units[0]["source_ids"]]
        encoded = compact_packet(units, events)
        assert expand_packet(encoded) == units
        assert len(encoded.encode()) < len(json.dumps(units, separators=(",", ":")).encode())
        assert len(json.loads(encoded)["sources"]) == len(
            {e["id"] for u in units for e in u["sources"]}
        )


def test_compact_selection_preserves_atomic_dependencies_and_fidelity(prepared_counter, tmp_path):
    store = Store(tmp_path / "db")
    for row in load_frozen(SOURCE)["cases"]:
        seed_graph(store, row["case"], row)
        for budget in (16, 128, 256, 512, 2000):
            values = packets(store, row["case"], load_case(row["case"]), budget, prepared_counter)
            context = values["compact"]["context"]
            assert prepared_counter.history_tokens(context) <= budget
            expanded = expand_packet(context)
            ids = {u["id"] for u in expanded}
            assert all(set(u["depends_on"]) <= ids for u in expanded)
            assert (
                values["compact_fixed"]["record_ids"]
                == values["structured"]["retrieval"]["record_ids"]
            )
            assert expand_packet(values["compact_fixed"]["context"]) == json.loads(
                values["structured"]["context"]
            )


def test_source_integrity_rejects_modified_histories_before_inference(tmp_path):
    path = tmp_path / "changed.json"
    path.write_bytes(SOURCE.read_bytes() + b" ")
    with pytest.raises(ValueError, match="exact published synthetic"):
        load_frozen(path)


def test_replay_is_paired_fresh_and_keeps_failures(prepared_counter, tmp_path):
    class Backend:
        calls = []

        def manifest(self, model):
            return prepared_counter.manifest["runtime"]

        def generate(self, model, system, prompt, schema, seed, **kwargs):
            self.calls.append((system, json.loads(prompt), seed, kwargs["json_schema"]))
            assert kwargs["counter"] is not None
            if len(self.calls) == 1:
                raise ModelFailure("retained offline error", {"raw": "invalid"}, "schema_error")
            answer = Continuation(facts={}, next_actions=[], complete=False, evidence_ids=[])
            return answer, {"parsed": answer.model_dump()}

    backend = Backend()
    result = run_representation(
        Store(tmp_path / "db"),
        backend,
        RepresentationRequest(budgets=[512], seeds=[42, 43]),
        SOURCE,
        tmp_path,
    )
    assert result["protocol"] == "representation-v1" and result["status"] == "completed"
    assert result["planned_trials"] == len(result["trials"]) == 30
    assert sum(t["status"] == "schema_error" for t in result["trials"]) == 1
    assert all(call[0] == READER_SYSTEM for call in backend.calls)
    for case in ("release_handoff", "conversation", "budgeting"):
        rows = [t for t in result["trials"] if t["case"] == case]
        assert {t["seed"] for t in rows} == {42, 43}
        assert (
            len(
                {
                    json.dumps(c[3], sort_keys=True)
                    for c in backend.calls
                    if c[1]["current_request"] == load_case(case).request
                }
            )
            == 1
        )
    for call in backend.calls:
        assert "expected_facts" not in json.dumps(call) and "grade" not in call[1]
    for trial in result["trials"]:
        if trial["token_budget"] and trial["status"] != "packet_error":
            assert trial["historical_tokens"] <= trial["token_budget"]
    assert (tmp_path / "runs" / f"{result['id']}.json").is_file()


def test_replay_obeys_shared_experiment_lock(tmp_path):
    with FileLock(tmp_path / "experiment.lock"):
        with pytest.raises(RuntimeError, match="Another local experiment"):
            run_representation(
                Store(tmp_path / "db"), None, RepresentationRequest(), SOURCE, tmp_path
            )


@pytest.mark.parametrize(
    "field,values",
    [("budgets", [0]), ("budgets", [128, 128]), ("seeds", [-1]), ("seeds", [42, 42])],
)
def test_replay_config_rejects_invalid_sweeps(field, values):
    with pytest.raises(ValueError):
        RepresentationRequest(**{field: values})
