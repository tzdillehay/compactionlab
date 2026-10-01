import json

import pytest
from filelock import FileLock

from compactionlab.experiment import continuation_schema, extraction_schema, run_experiment
from compactionlab.fixtures import load_case
from compactionlab.schemas import (
    Continuation,
    ExperimentRequest,
    MemoryExtraction,
    MemoryRecord,
    Summary,
)
from compactionlab.store import Store


class RecordingBackend:
    def __init__(self, invalid_source=False):
        self.calls = []
        self.invalid_source = invalid_source

    def manifest(self, name):
        return {"name": name, "digest": "offline-test-only"}

    def generate(
        self, model, system, prompt, schema, seed, json_schema=None, *, settings=None, counter=None
    ):
        self.calls.append(
            {
                "model": model,
                "system": system,
                "prompt": prompt,
                "seed": seed,
                "schema": json_schema,
                "settings": settings.model_dump() if settings else None,
            }
        )
        if schema is Summary:
            answer = Summary(summary="Offline test summary, not a live model result.")
        elif schema is MemoryExtraction:
            first = json.loads(prompt)[0]
            answer = MemoryExtraction(
                records=[
                    MemoryRecord(
                        id="record",
                        kind="fact",
                        text=first["text"],
                        source_ids=["missing" if self.invalid_source else first["id"]],
                    )
                ]
            )
        else:
            answer = Continuation(facts={}, next_actions=[], complete=False, evidence_ids=[])
        return answer, {"parsed": answer.model_dump(), "request": {"messages": [prompt]}}


def test_fresh_conditions_share_contract_and_failures_are_retained(tmp_path):
    backend = RecordingBackend()
    result = run_experiment(
        Store(tmp_path / "db"),
        backend,
        ExperimentRequest(
            writer_model="writer", reader_model="reader", cases=["conversation"], byte_budget=1000
        ),
        tmp_path,
    )
    assert result["protocol"] == "state-probe-v4"
    assert len(result["trials"]) == 5
    assert all(t["status"] == "graded" and not t["grade"]["passed"] for t in result["trials"])
    calls = [call for call in backend.calls if call["model"] == "reader"]
    assert len(calls) == 5
    assert len({call["system"] for call in calls}) == 1
    assert len({json.dumps(call["schema"], sort_keys=True) for call in calls}) == 1
    for call in backend.calls:
        assert "expected_facts" not in call["prompt"] and "fact_accuracy" not in call["prompt"]
    for trial in result["trials"]:
        if trial["condition"] != "full_history":
            assert trial["context_bytes"] <= 1000
    assert (tmp_path / "runs" / f"{result['id']}.json").is_file()


def test_writer_error_does_not_erase_other_conditions(tmp_path):
    result = run_experiment(
        Store(tmp_path / "db"),
        RecordingBackend(invalid_source=True),
        ExperimentRequest(cases=["conversation"]),
        tmp_path,
    )
    errors = {t["condition"] for t in result["trials"] if t["status"] == "writer_error"}
    assert errors == {"plain", "structured"}
    assert len(result["trials"]) == 5
    assert "memory_error" in result["cases"][0]


def test_schema_contracts_constrain_format_without_supplying_answers():
    case = load_case("budgeting")
    schema = continuation_schema(case)
    field = schema["properties"]["facts"]["properties"]["budget_cents"]
    assert "90000" not in json.dumps(field)
    assert field["pattern"] == r"^(unknown|[0-9]+)$"
    writer_schema = extraction_schema([event.model_dump() for event in case.events])
    allowed = writer_schema["$defs"]["MemoryRecord"]["properties"]["source_ids"]["items"]["enum"]
    assert set(allowed) == {event.id for event in case.events}
    assert "user" not in allowed


def test_categorical_contracts_offer_alternatives_not_the_correct_answer():
    schema = continuation_schema(load_case("conversation"))
    fields = schema["properties"]["facts"]["properties"]
    assert fields["approved"]["enum"] == ["true", "false", "unknown"]
    assert fields["pending"]["enum"] == [
        "address_confirmation",
        "approval_confirmation",
        "none",
        "unknown",
    ]


def test_experiments_are_serialized_across_clients(tmp_path):
    with FileLock(tmp_path / "experiment.lock"):
        with pytest.raises(RuntimeError, match="Another local experiment"):
            run_experiment(
                Store(tmp_path / "db"),
                RecordingBackend(),
                ExperimentRequest(cases=["conversation"]),
                tmp_path,
            )


def test_all_compressed_conditions_enforce_serialized_token_allowance(prepared_counter, tmp_path):
    class Backend(RecordingBackend):
        def manifest(self, name):
            return prepared_counter.manifest["runtime"]

    backend = Backend()
    result = run_experiment(
        Store(tmp_path / "db"),
        backend,
        ExperimentRequest(cases=["conversation"], token_budget=100),
        tmp_path,
    )
    assert result["tokenizer"]["scope"] == "offline-test-only"
    for trial in result["trials"]:
        if trial["status"] == "graded":
            assert trial["historical_tokens"] == prepared_counter.history_tokens(trial["context"])
            if trial["condition"] != "full_history":
                assert trial["historical_tokens"] <= 100
    assert (
        next(t for t in result["trials"] if t["condition"] == "full_history")["historical_tokens"]
        > 100
    )
