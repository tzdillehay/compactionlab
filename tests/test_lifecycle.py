import json

import pytest
from filelock import FileLock

from compactionlab.lifecycle import CONDITIONS, run_lifecycle
from compactionlab.lifecycle_analysis import analyze
from compactionlab.lifecycle_cases import generate_cases, make_case
from compactionlab.lifecycle_grading import grade
from compactionlab.lifecycle_memory import current_heads, encode, load_memory, retrieve, seed_memory
from compactionlab.lifecycle_types import LedgerEvent, LifecycleAnswer, LifecycleRequest
from compactionlab.ollama import ModelFailure
from compactionlab.store import Store


def answer(case, **changes):
    return LifecycleAnswer.model_validate(
        {
            "facts": case.expected_facts,
            "next_actions": case.ready_actions,
            "completed_actions": case.completed_actions,
            "complete": case.complete,
            "fact_source_ids": case.fact_ids,
            "completion_evidence_ids": case.completion_ids,
            **changes,
        }
    )


def test_fixtures_cover_state_and_placement_without_changed_truth():
    cases = generate_cases(314159)
    assert len(cases) == 40 and len({c.id for c in cases}) == 40
    assert cases == generate_cases(314159)
    for old, recent in zip(cases[::2], cases[1::2], strict=True):
        assert {r.id: r for r in old.entries} == {r.id: r for r in recent.entries}
        assert old.expected_facts == recent.expected_facts
        assert old.ready_actions == recent.ready_actions
        assert grade(old, answer(old))["passed"]
        assert grade(recent, answer(recent))["passed"]
    following = make_case("budgeting", "followup_pending", "old", 314159)
    assert following.ready_actions == ["request_approval"]
    assert following.completed_actions == ["prepare_budget"] and not following.complete


def test_grader_separates_citation_errors_from_behavior_and_stale_receipts():
    case = make_case("release_handoff", "completed", "recent", 314159)
    repeated = grade(case, answer(case, next_actions=["verify_release"]))
    assert repeated["repeated_actions"] == ["verify_release"]
    assert not repeated["behavior_passed"]
    uncited = grade(case, answer(case, fact_source_ids=[]))
    assert uncited["behavior_passed"] and not uncited["passed"]
    reopened = make_case("release_handoff", "reopened", "recent", 314159)
    stale = grade(
        reopened, answer(reopened, complete=True, completion_evidence_ids=["e004", "e005"])
    )
    assert stale["false_completion"] and not stale["checks"]["completion_evidence"]
    canceled = make_case("conversation", "canceled", "old", 314159)
    assert not grade(canceled, answer(canceled, next_actions=["schedule_delivery"]))["passed"]


def test_sqlite_roundtrip_preserves_revisions_sources_and_cancellation(tmp_path):
    store = Store(tmp_path / "memory.sqlite3")
    for case in generate_cases(314159):
        seed_memory(store, case.id, case.entries)
        loaded = load_memory(store, case.id)
        assert encode(loaded) == encode(case.entries)
        heads = current_heads(loaded)
        assert heads["primary"].id != "guess"
        assert heads["primary"].state == case.expected_facts["task_state"]
        assert heads["requirement"].revision == case.expected_facts["revision"]


def test_linked_retrieval_is_atomic_and_same_revision(prepared_counter):
    goal = LedgerEvent(
        id="g", entity="goal", kind="goal", source="user", text="target", revision="R2"
    )
    task = LedgerEvent(
        id="t",
        entity="task",
        kind="task",
        source="user",
        text="target",
        revision="R2",
        state="pending",
        requires=["goal"],
    )
    entries = [goal, task]
    budget = prepared_counter.history_tokens(encode([task]))
    packet = retrieve(entries, "target", budget, prepared_counter, "linked_current")
    assert "t" not in packet["record_ids"]
    assert prepared_counter.history_tokens(packet["context"]) <= budget
    enough = prepared_counter.history_tokens(encode(entries))
    assert retrieve(entries, "target", enough, prepared_counter, "linked_current")[
        "context"
    ] == encode(entries)
    assert retrieve(entries, "target", enough, prepared_counter, "current_no_links")[
        "context"
    ] == encode(entries)
    with pytest.raises(ValueError, match="another revision"):
        retrieve(
            [goal.model_copy(update={"revision": "R1"}), task],
            "target",
            enough,
            prepared_counter,
            "linked_current",
        )


def test_recent_packet_is_contiguous_not_best_fit(prepared_counter):
    events = [
        LedgerEvent(id=str(i), entity=str(i), kind="note", source="user", text=text)
        for i, text in enumerate(["short", "large " * 300, "latest"])
    ]
    allowance = prepared_counter.history_tokens(encode([events[-1], events[0]]))
    assert retrieve(events, "short", allowance, prepared_counter, "recent_history")[
        "record_ids"
    ] == ["2"]


def test_runner_retains_writer_and_reader_errors_and_respects_lock(
    tmp_path, prepared_counter, monkeypatch
):
    import compactionlab.lifecycle as runner

    cases = generate_cases(314159)[:2]
    monkeypatch.setattr(runner, "generate_cases", lambda seed: cases)
    calls = []

    class FailingBackend:
        def manifest(self, model):
            return prepared_counter.manifest["runtime"]

        def generate(self, *args, **kwargs):
            calls.append(args)
            assert "expected_facts" not in args[2] and "ready_actions" not in args[2]
            raise ModelFailure("offline injected error", {"request": {"prompt": args[2]}})

    result = run_lifecycle(
        Store(tmp_path / "memory.sqlite3"), FailingBackend(), LifecycleRequest(), tmp_path
    )
    assert result["status"] == "completed"
    assert len(result["trials"]) == 2 * len(CONDITIONS)
    assert len(calls) == 14  # Two writers, twelve readers; failed summaries are never replaced.
    assert sum(t["status"] == "writer_error" for t in result["trials"]) == 2
    assert all(total["passed"] == 0 and total["errors"] == 2 for total in result["totals"].values())
    assert result["analysis"]["control_supported_cases"] == []
    saved = json.loads((tmp_path / "runs" / f"{result['id']}.json").read_text())
    assert saved == result
    with FileLock(tmp_path / "experiment.lock"), pytest.raises(RuntimeError, match="Another local"):
        run_lifecycle(
            Store(tmp_path / "other.sqlite3"), FailingBackend(), LifecycleRequest(), tmp_path
        )


def test_paired_analysis_keeps_errors_and_unsupported_controls_visible():
    rows = []
    for case in ("a", "b"):
        for condition in CONDITIONS:
            passed = condition == "linked_current" or (
                case == "a" and condition in {"full_history", "minimal_source"}
            )
            rows.append(
                {
                    "case": case,
                    "condition": condition,
                    "status": "graded",
                    "context": condition,
                    "workflow": "conversation",
                    "checkpoint": "pending",
                    "placement": "old",
                    "grade": {"behavior_passed": passed, "passed": passed},
                }
            )
    result = analyze(rows)
    assert result["control_supported_cases"] == ["a"]
    assert result["control_excluded_cases"] == ["b"]
    assert result["paired"]["all"]["lexical"]["behavior_passed"] == {
        "pairs": 2,
        "wins": 2,
        "losses": 0,
        "ties": 0,
    }
    assert result["paired"]["control_supported"]["lexical"]["behavior_passed"]["pairs"] == 1
