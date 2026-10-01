import hashlib
import json
from pathlib import Path

from compactionlab.lifecycle import CONDITIONS, SUMMARY_SYSTEM, SYSTEM, source_hashes, summarize
from compactionlab.lifecycle_analysis import analyze
from compactionlab.lifecycle_cases import answer_schema, generate_cases
from compactionlab.lifecycle_grading import grade
from compactionlab.lifecycle_memory import current_heads, encode
from compactionlab.lifecycle_types import LifecycleAnswer, LifecycleRequest

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_lifecycle_trace_coverage_source_fidelity_and_independent_grading():
    folder = ROOT / "results/lifecycle-2026-10-01"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected
    assert manifest["frozen_source_commit"] == "da4b6e6eec4d43215fb4d9162a2302747ac5bafc"
    result = json.loads((folder / f"{manifest['run_ids'][0]}.json").read_text(encoding="utf-8"))
    config = LifecycleRequest.model_validate(result["config"])
    cases = {c.id: c for c in generate_cases(config.seed)}
    assert result["source_sha256"] == source_hashes()
    assert result["protocol"] == "lifecycle-v1" and result["status"] == "completed"
    assert result["memory_origin"] == "typed_api_events"
    assert len(cases) == 40
    assert len(result["trials"]) == result["planned_trials"] == 280
    assert {(t["case"], t["condition"]) for t in result["trials"]} == {
        (c, condition) for c in cases for condition in CONDITIONS
    }
    assert result["totals"] == summarize(result["trials"])
    assert result["analysis"] == analyze(result["trials"])
    for saved in result["cases"]:
        case = cases[saved["case"]]
        assert saved["entries"] == [e.packet() for e in case.entries]
        writer = saved["summary_writer"]
        assert writer["request"]["messages"] == [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": encode(case.entries)},
        ]
        assert writer["request"]["options"] == config.reader_settings.options(config.seed)
        if "prompt_tokens" in writer:
            assert writer["expected_prompt_tokens"] == writer["prompt_tokens"]
            assert writer["prompt_accounting_match"] is True
    for trial in result["trials"]:
        case = cases[trial["case"]]
        if trial["status"] == "writer_error":
            continue
        assert len(trial["context"].encode()) == trial["context_bytes"]
        if trial["token_budget"] is not None:
            assert trial["historical_tokens"] <= trial["token_budget"] == config.token_budget
        if trial["condition"] != "summary":
            selected = [e for e in case.entries if e.id in trial["record_ids"]]
            assert trial["context"] == encode(selected)
            if trial["condition"] == "full_history":
                assert selected == case.entries
            elif trial["condition"] == "minimal_source":
                assert set(trial["record_ids"]) == set(case.minimal_ids)
            elif trial["condition"] in {"current_no_links", "linked_current"}:
                heads = current_heads(case.entries)
                assert all(e == heads[e.entity] for e in selected)
                assert "guess" not in trial["record_ids"]
                if trial["condition"] == "linked_current":
                    entities = {e.entity: e for e in selected}
                    assert all(set(e.requires) <= entities.keys() for e in selected)
                    assert all(
                        entities[parent].revision == e.revision
                        for e in selected
                        for parent in e.requires
                    )
        observation = trial.get("model", {})
        if "prompt_tokens" in observation:
            assert observation["prompt_accounting_match"] is True
            assert observation["expected_prompt_tokens"] == observation["prompt_tokens"]
            request = observation["request"]
            assert len(request["messages"]) == 2
            assert request["messages"][0] == {"role": "system", "content": SYSTEM}
            assert json.loads(request["messages"][1]["content"]) == {
                "historical_context": trial["context"],
                "current_request": case.request,
                "allowed_actions": case.actions,
            }
            assert request["format"] == answer_schema(case)
            assert request["options"] == config.reader_settings.options(config.seed)
        if trial["status"] == "graded":
            assert trial["grade"] == grade(
                case, LifecycleAnswer.model_validate(observation["parsed"])
            )
