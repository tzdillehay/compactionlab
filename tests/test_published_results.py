import hashlib
import json
from pathlib import Path

from compactionlab.experiment import aggregate
from compactionlab.grading import grade
from compactionlab.qualification import summarize
from compactionlab.qualification_cases import generate_cases, grade_qualification
from compactionlab.schemas import Continuation, QualificationRequest

ROOT = Path(__file__).resolve().parents[1]


def test_published_trace_integrity_and_independent_grades():
    folder = ROOT / "results/smoke-2026-10-01"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    count = 0
    for name, expected_hash in manifest["sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected_hash
    for identifier in manifest["run_ids"]:
        result = json.loads((folder / f"{identifier}.json").read_text(encoding="utf-8"))
        assert result["protocol"] == "state-probe-v3"
        assert result["totals"] == aggregate(result["trials"])
        for trial in result["trials"]:
            count += 1
            if trial["status"] == "graded":
                answer = Continuation.model_validate(trial["model"]["parsed"])
                assert trial["grade"] == grade(trial["case"], answer)
                assert len(trial["context"].encode()) == trial["context_bytes"]
                if trial["condition"] != "full_history":
                    assert trial["context_bytes"] <= result["config"]["byte_budget"]
    assert count == 90


def test_published_qualification_integrity_coverage_and_independent_grades():
    folder = ROOT / "results/qualification-2026-10-01"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected_hash
    runs = [
        json.loads((folder / f"{identifier}.json").read_text(encoding="utf-8"))
        for identifier in manifest["run_ids"]
    ]
    assert len(runs) == 2
    assert [r["config"]["settings"]["thinking"] for r in runs] == [False, True]
    assert runs[0]["source_sha256"] == runs[1]["source_sha256"]
    assert runs[0]["model"]["digest"] == runs[1]["model"]["digest"]
    assert runs[0]["tokenizer"] == runs[1]["tokenizer"]
    count = 0
    for result in runs:
        assert result["protocol"] == "qualification-v3" and result["status"] == "completed"
        config = QualificationRequest.model_validate(result["config"])
        cases = {case.id: case for case in generate_cases(config)}
        saved_cases = {case["id"]: case for case in result["cases"]}
        assert set(cases) == set(saved_cases)
        expected_pairs = {
            (case, condition) for case in cases for condition in ("full_history", "minimal_source")
        }
        assert len(result["trials"]) == len(expected_pairs)
        assert {(t["case"], t["condition"]) for t in result["trials"]} == expected_pairs
        assert result["totals"] == summarize(result["trials"], config.workflows)
        for trial in result["trials"]:
            count += 1
            case = cases[trial["case"]]
            events = [
                event.model_dump()
                for event in case.events
                if trial["condition"] == "full_history" or event.id in case.minimal_ids
            ]
            saved = saved_cases[case.id]
            assert saved["events"] == [event.model_dump() for event in case.events]
            if "calculator_observation" in saved:
                events.append(saved["calculator_observation"]["event"])
            assert json.loads(trial["context"]) == events
            assert len(trial["context"].encode()) == trial["context_bytes"]
            if "prompt_tokens" in trial["model"]:
                assert trial["model"]["expected_prompt_tokens"] == trial["model"]["prompt_tokens"]
                assert trial["model"]["prompt_accounting_match"] is True
            if trial["status"] == "graded":
                answer = Continuation.model_validate(trial["model"]["parsed"])
                assert trial["grade"] == grade_qualification(case, answer)
    assert count == 240


def test_published_token_stress_smoke_preserves_errors_and_enforces_allowance():
    folder = ROOT / "results/token-budget-2026-10-01"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected_hash
    assert len(manifest["run_ids"]) == 1
    result = json.loads((folder / f"{manifest['run_ids'][0]}.json").read_text(encoding="utf-8"))
    assert result["protocol"] == "state-probe-v4" and result["status"] == "completed"
    assert result["config"]["token_budget"] == 128
    assert len(result["trials"]) == 15
    assert result["totals"] == aggregate(result["trials"])
    for trial in result["trials"]:
        if "context" in trial:
            assert len(trial["context"].encode()) == trial["context_bytes"]
            if trial["condition"] == "full_history":
                assert trial["historical_tokens"] > result["config"]["token_budget"]
            else:
                assert trial["historical_tokens"] <= result["config"]["token_budget"]
        if "prompt_tokens" in trial.get("model", {}):
            assert trial["model"]["expected_prompt_tokens"] == trial["model"]["prompt_tokens"]
            assert trial["model"]["prompt_accounting_match"] is True
        if trial["status"] == "graded":
            answer = Continuation.model_validate(trial["model"]["parsed"])
            assert trial["grade"] == grade(trial["case"], answer)
