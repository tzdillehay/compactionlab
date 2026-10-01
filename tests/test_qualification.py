import json
import random

import pytest
from filelock import FileLock

from compactionlab.calculator import draft_snowball
from compactionlab.grading import snowball_reference
from compactionlab.qualification import run_qualification, summarize
from compactionlab.qualification_cases import answer_schema, generate_cases, grade_qualification
from compactionlab.schemas import Continuation, InferenceSettings, QualificationRequest


def test_cases_vary_values_and_include_both_completion_states():
    config = QualificationRequest(cases_per_workflow=4)
    cases = generate_cases(config)
    assert len(cases) == 12
    for workflow in config.workflows:
        rows = [c for c in cases if c.workflow == workflow]
        assert {c.complete for c in rows} == {True, False}
        assert len({json.dumps(c.expected_facts, sort_keys=True) for c in rows}) == 4
    for case in cases:
        answer = Continuation(
            facts=case.expected_facts,
            next_actions=case.required_actions,
            complete=case.complete,
            evidence_ids=case.evidence_ids,
        )
        assert grade_qualification(case, answer)["passed"]
        wrong = answer.model_copy(update={"complete": not case.complete})
        assert not grade_qualification(case, wrong)["passed"]
        assert set(case.minimal_ids) <= {e.id for e in case.events}
        contract = answer_schema(case)
        assert "expected_facts" not in json.dumps(contract)


def test_evidence_requires_current_observation_but_allows_supporting_sources():
    case = generate_cases(
        QualificationRequest(cases_per_workflow=4, workflows=["release_handoff"])
    )[2]
    answer = Continuation(
        facts=case.expected_facts,
        next_actions=[],
        complete=True,
        evidence_ids=["test-B", "artifact-current"],
    )
    assert grade_qualification(case, answer)["passed"]
    for bad_ids in (["artifact-current"], ["test-A"], ["test-B", "completion-A"]):
        assert not grade_qualification(case, answer.model_copy(update={"evidence_ids": bad_ids}))[
            "passed"
        ]


def test_public_calculator_agrees_with_independent_reference():
    rng = random.Random(420)
    for _ in range(100):
        balances = {name: rng.randrange(0, 1000) for name in ["a", "b", "c"]}
        minimums = {name: rng.randrange(0, 100) for name in balances}
        budget = sum(min(balances[n], minimums[n]) for n in balances) + rng.randrange(0, 2000)
        result = draft_snowball(balances, minimums, budget)
        assert result["payments"] == snowball_reference(balances, minimums, budget)
        assert sum(result["payments"].values()) + result["unallocated_cents"] == budget
    with pytest.raises(ValueError):
        draft_snowball({"a": 100}, {"a": 10}, 1)
    with pytest.raises(ValueError):
        draft_snowball({"a": 100}, {"a": 10}, True)


def test_gate_counts_errors_and_does_not_qualify_small_smokes():
    def rows(n, passed, condition="full_history"):
        return [
            {
                "workflow": "conversation",
                "condition": condition,
                "status": "graded" if i < passed else "output_error",
                "grade": {"passed": i < passed},
            }
            for i in range(n)
        ]

    assert not summarize(rows(4, 4), ["conversation"])["conversation"]["qualified"]
    assert summarize(rows(20, 18), ["conversation"])["conversation"]["qualified"]
    assert not summarize(rows(20, 17), ["conversation"])["conversation"]["qualified"]
    assert not summarize(rows(20, 20, "minimal_source"), ["conversation"])["conversation"][
        "qualified"
    ]


def test_runner_retains_failures_and_keeps_grader_out_of_requests(prepared_counter, tmp_path):
    from compactionlab.ollama import ModelFailure

    calls = []

    class Backend:
        def manifest(self, name):
            return prepared_counter.manifest["runtime"]

        def generate(self, model, system, prompt, schema, seed, **kwargs):
            calls.append(json.loads(prompt))
            raise ModelFailure(
                "offline failure", {"request": {"messages": [prompt]}}, kind="output_error"
            )

    config = QualificationRequest(cases_per_workflow=4, workflows=["budgeting"])
    result = run_qualification(Backend(), config, tmp_path)
    assert len(result["trials"]) == 8 and not result["qualified"]
    assert result["totals"]["budgeting"]["full_history"]["errors"] == 4
    assert all("expected_facts" not in json.dumps(call) for call in calls)
    assert all("calculator-draft" in call["historical_context"] for call in calls)
    assert (tmp_path / "qualifications" / f"{result['id']}.json").is_file()
    with FileLock(tmp_path / "experiment.lock"), pytest.raises(RuntimeError, match="Another"):
        run_qualification(Backend(), config, tmp_path)


def test_output_reserve_and_duplicate_workflows_are_rejected():
    with pytest.raises(ValueError):
        InferenceSettings(context_tokens=2048, max_output_tokens=2048)
    with pytest.raises(ValueError):
        QualificationRequest(workflows=["conversation", "conversation"])
