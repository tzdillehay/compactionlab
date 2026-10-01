import pytest

from compactionlab.fixtures import load_case
from compactionlab.grading import grade, snowball_reference
from compactionlab.schemas import Continuation


def release_answer(**kwargs):
    values = dict(
        facts={
            "threshold_cents": "7500",
            "fee_cents": "499",
            "revision": "B",
            "validation": "pending",
        },
        next_actions=["update_tests", "run_tests"],
        complete=False,
        evidence_ids=[],
    )
    values.update(kwargs)
    return Continuation(**values)


def test_actual_test_observation_and_unfinished_revision():
    case = load_case("release_handoff")
    log = next(event.text for event in case.events if event.id == "test-A")
    assert "exit 0" in log and "2 assertions passed" in log
    assert grade(case.id, release_answer())["passed"]


@pytest.mark.parametrize(
    "changes",
    [
        {"complete": True},
        {"evidence_ids": ["test-A"]},
        {"next_actions": ["run_tests"]},
        {
            "facts": {
                "threshold_cents": "5000",
                "fee_cents": "499",
                "revision": "B",
                "validation": "passed",
            }
        },
        {"next_actions": ["update_tests", "run_tests", "declare_complete"]},
    ],
)
def test_stale_evidence_false_completion_and_lost_requirements_fail(changes):
    assert not grade("release_handoff", release_answer(**changes))["passed"]


def test_reference_budget_and_rollover():
    balances = {"pine": 60000, "oak": 300000, "cedar": 700000}
    minimums = {"pine": 10000, "oak": 25000, "cedar": 15000}
    assert snowball_reference(balances, minimums, 90000) == {
        "pine": 50000,
        "oak": 25000,
        "cedar": 15000,
    }
    assert snowball_reference(balances, minimums, 120000) == {
        "pine": 60000,
        "oak": 45000,
        "cedar": 15000,
    }
    with pytest.raises(ValueError):
        snowball_reference(balances, minimums, 100)


def test_budget_caps_at_balances_and_ties_are_named():
    assert snowball_reference({"b": 100, "a": 100}, {"b": 0, "a": 0}, 50) == {"a": 50, "b": 0}
    assert sum(snowball_reference({"a": 100}, {"a": 10}, 500).values()) == 100


def test_missing_facts_not_rescued_by_honest_incomplete():
    answer = Continuation(facts={}, next_actions=["ask_address"], complete=False, evidence_ids=[])
    result = grade("conversation", answer)
    assert result["checks"]["honest_completion"]
    assert not result["passed"]
