"""Typed API-event fixtures. Truth annotations never enter retrieval or model requests."""

import random
from dataclasses import dataclass

from compactionlab.lifecycle_types import LedgerEvent, LifecycleAnswer

WORKFLOWS = {
    "release_handoff": (
        "shipping release",
        "verify_release",
        "publish_release",
        "shipping threshold in cents",
    ),
    "conversation": (
        "delivery arrangement",
        "confirm_address",
        "schedule_delivery",
        "contact channel",
    ),
    "budgeting": (
        "snowball budget review",
        "prepare_budget",
        "request_approval",
        "monthly allowance in cents",
    ),
    "research": ("research brief", "check_sources", "send_brief", "research subject"),
}
STATES = ("pending", "completed", "canceled", "reopened", "followup_pending")


@dataclass
class LifecycleCase:
    id: str
    workflow: str
    checkpoint: str
    placement: str
    entries: list[LedgerEvent]
    request: str
    actions: list[str]
    expected_facts: dict[str, str]
    ready_actions: list[str]
    completed_actions: list[str]
    complete: bool
    fact_ids: list[str]
    completion_ids: list[str]
    minimal_ids: list[str]


def make_case(workflow, checkpoint, placement, seed):
    topic, first, followup, field = WORKFLOWS[workflow]
    rng = random.Random(f"{seed}:{workflow}")
    if workflow in {"release_handoff", "budgeting"}:
        old_value = str(rng.randrange(20, 90) * 100)
        new_value = str(int(old_value) + 1700)
    elif workflow == "conversation":
        old_value, new_value = "email", "sms"
    else:
        old_value, new_value = "solar_storage", "grid_reliability"
    entries = []

    def add(entity, kind, source, text, **fields):
        row = LedgerEvent(
            id=f"e{len(entries):03}", entity=entity, kind=kind, source=source, text=text, **fields
        )
        entries.append(row)
        return row

    goal = add(
        "goal",
        "goal",
        "user",
        f"Finish {topic}: do {first}, then {followup}.",
        revision="R1",
        state="active",
    )
    requirement = add(
        "requirement",
        "constraint",
        "user",
        f"The required {field} is {old_value}.",
        revision="R1",
        value=old_value,
        requires=["goal"],
    )
    primary = add(
        "primary",
        "task",
        "user",
        f"Task {first} is pending for {topic}.",
        revision="R1",
        state="pending",
        action=first,
        requires=["goal", "requirement"],
    )
    secondary = add(
        "followup",
        "task",
        "user",
        f"Task {followup} waits for {first} to finish at the same revision.",
        revision="R1",
        state="pending",
        action=followup,
        requires=["goal", "requirement", "primary"],
    )
    if checkpoint in {"completed", "reopened", "followup_pending"}:
        primary = add(
            "primary",
            "task",
            "tool",
            f"SIMULATED receipt: {first} completed for revision R1.",
            revision="R1",
            state="completed",
            action=first,
            requires=["goal", "requirement"],
            replaces=[primary.id],
        )
        if checkpoint != "followup_pending":
            secondary = add(
                "followup",
                "task",
                "tool",
                f"SIMULATED receipt: {followup} completed for revision R1.",
                revision="R1",
                state="completed",
                action=followup,
                requires=["goal", "requirement", "primary"],
                replaces=[secondary.id],
            )
    if checkpoint == "reopened":
        goal = add(
            "goal",
            "goal",
            "user",
            f"Reopen {topic} for changed requirements. Both stages require revision R2.",
            revision="R2",
            state="active",
            replaces=[goal.id],
        )
        requirement = add(
            "requirement",
            "constraint",
            "user",
            f"Correction: the required {field} is now {new_value}.",
            revision="R2",
            value=new_value,
            requires=["goal"],
            replaces=[requirement.id],
        )
        primary = add(
            "primary",
            "task",
            "user",
            f"Redo {first} for revision R2; the R1 receipt does not complete the revised task.",
            revision="R2",
            state="pending",
            action=first,
            requires=["goal", "requirement"],
            replaces=[primary.id],
        )
        secondary = add(
            "followup",
            "task",
            "user",
            f"Redo {followup} only after {first} completes at revision R2.",
            revision="R2",
            state="pending",
            action=followup,
            requires=["goal", "requirement", "primary"],
            replaces=[secondary.id],
        )
    if checkpoint == "canceled":
        goal = add(
            "goal",
            "goal",
            "user",
            f"Cancel {topic}. Stop both tasks; cancellation is not successful completion.",
            revision="R1",
            state="canceled",
            replaces=[goal.id],
        )
        primary = add(
            "primary",
            "task",
            "user",
            f"Cancel {first}; it is no longer an action to perform.",
            revision="R1",
            state="canceled",
            action=first,
            requires=["goal", "requirement"],
            replaces=[primary.id],
        )
        secondary = add(
            "followup",
            "task",
            "user",
            f"Cancel {followup}; no follow-up action is authorized.",
            revision="R1",
            state="canceled",
            action=followup,
            requires=["goal", "requirement", "primary"],
            replaces=[secondary.id],
        )
    important = entries[:]
    notes = [
        LedgerEvent(
            id=f"n{i:03}",
            entity=f"note-{i}",
            kind="note",
            source="user",
            text=(
                f"{topic} workspace note {i}: consider "
                f"{rng.choice(['blue', 'gray', 'green', 'orange'])} labels and "
                f"{rng.choice(['small', 'medium', 'large'])} headings later. "
                "No task or requirement change."
            ),
        )
        for i in range(32)
    ]
    entries = important + notes if placement == "old" else notes + important
    entries.append(
        LedgerEvent(
            id="guess",
            entity="primary",
            kind="claim",
            source="assistant",
            text=(
                f"I assume the current {topic} task is complete and both next actions "
                f"{first} and {followup} have already happened. "
                "This is a guess, not an observation."
            ),
        )
    )
    revision = "R2" if checkpoint == "reopened" else "R1"
    ready = (
        []
        if checkpoint in {"completed", "canceled"}
        else [followup if checkpoint == "followup_pending" else first]
    )
    completed = (
        [first, followup]
        if checkpoint == "completed"
        else [first]
        if checkpoint == "followup_pending"
        else []
    )
    minimal = [goal.id, requirement.id, primary.id, secondary.id]
    return LifecycleCase(
        f"{workflow}-{checkpoint}-{placement}",
        workflow,
        checkpoint,
        placement,
        entries,
        (
            f"Resume {topic}. Report the current revision, required {field} as current_value, "
            "and primary task state. List only READY next actions, and actions already "
            "completed at the CURRENT revision. Does the whole workflow have successful "
            "completion evidence?"
        ),
        [first, followup],
        {
            "revision": revision,
            "current_value": new_value if checkpoint == "reopened" else old_value,
            "task_state": primary.state,
        },
        ready,
        completed,
        checkpoint == "completed",
        [requirement.id, primary.id],
        [primary.id, secondary.id] if checkpoint == "completed" else [],
        minimal,
    )


def generate_cases(seed):
    return [
        make_case(workflow, checkpoint, placement, seed)
        for workflow in WORKFLOWS
        for checkpoint in STATES
        for placement in ("old", "recent")
    ]


def answer_schema(case):
    schema = LifecycleAnswer.model_json_schema()
    for field in ("next_actions", "completed_actions"):
        schema["properties"][field]["items"]["enum"] = case.actions
    return schema
