"""Parameterized capability calibration, separate from the published pilot."""

import random
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from compactionlab.grading import snowball_reference
from compactionlab.schemas import Continuation, Event


@dataclass
class QualificationCase:
    id: str
    workflow: str
    events: list[Event]
    minimal_ids: list[str]
    request: str
    expected_facts: dict[str, str]
    required_actions: list[str]
    prohibited_actions: list[str]
    complete: bool
    evidence_ids: list[str]
    categories: dict[str, list[str]]
    calculator_input: dict | None = None


def event(identifier, source, text):
    return Event(id=identifier, source=source, text=text)


def test_shipping(threshold, fee):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / "shipping.py").write_text(
            f"def shipping(cents):\n    return 0 if cents >= {threshold} else {fee}\n",
            encoding="utf-8",
        )
        (path / "check.py").write_text(
            "from shipping import shipping\n"
            f"assert shipping({threshold - 1}) == {fee}\n"
            f"assert shipping({threshold}) == 0\n"
            f"assert shipping({threshold + 1}) == 0\n"
            "print('3 boundary assertions passed')\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, "check.py"], cwd=path, check=True, text=True, capture_output=True
        )
        return result.stdout.strip()


def release_case(index, rng):
    old = rng.randrange(20, 80) * 100
    threshold = old + rng.randrange(5, 25) * 100
    fee = rng.choice([199, 399, 499, 799])
    branch = index % 4
    corrected, updated, tested = branch != 3, branch != 1, branch in (2, 3)
    current = threshold if corrected else old
    revision = "B" if corrected and updated else "A"
    events = [
        event(
            "requirement-A",
            "user",
            f"Shipping is free at or above {old} cents, otherwise {fee} cents. "
            "Verify current requirements before declaring completion.",
        ),
        event(
            "test-A",
            "tool",
            f"Revision A implements threshold {old}, fee {fee}. Exit 0: {test_shipping(old, fee)}.",
        ),
        event("completion-A", "assistant", "Revision A was completed and verified."),
    ]
    if corrected:
        events.append(
            event(
                "requirement-B",
                "user",
                f"Correction: threshold is now {threshold} cents inclusive; "
                f"the {fee}-cent fee is unchanged. Apply and verify this change.",
            )
        )
    else:
        events.append(
            event(
                "confirmation",
                "user",
                f"Keep the {old}-cent threshold and {fee}-cent fee. "
                "No implementation change is needed.",
            )
        )
    events.append(
        event(
            "artifact-current",
            "tool",
            f"Current revision {revision} implements threshold "
            f"{current if updated else old}, fee {fee}.",
        )
    )
    if corrected and tested:
        events.append(
            event(
                "test-B",
                "tool",
                f"Revision B: exit 0, {test_shipping(current, fee)}. "
                "Checked against current requirements.",
            )
        )
    elif corrected:
        events.append(
            event(
                "pending",
                "tool",
                "Assertions still describe revision A. "
                "No validation of the corrected requirements has been run.",
            )
        )
    events.append(
        event(
            "distraction",
            "user",
            "Later we could improve typography. Keep the current shipping requirement.",
        )
    )
    complete = tested
    return QualificationCase(
        f"release-{index:03}",
        "release_handoff",
        events,
        [
            "requirement-B" if corrected else "confirmation",
            "artifact-current",
            "test-B" if corrected and tested else ("test-A" if tested else "pending"),
        ],
        "Report current required threshold and fee in cents, implementation revision "
        "and validation state. Identify required next actions and cite only evidence "
        "of current completion.",
        {
            "threshold_cents": str(current),
            "fee_cents": str(fee),
            "revision": revision,
            "validation": "passed" if tested else "pending",
        },
        []
        if complete
        else (["update_implementation"] if not updated else []) + ["update_tests", "run_tests"],
        [] if complete else ["declare_complete"],
        complete,
        ["test-B" if corrected else "test-A"] if complete else [],
        {"validation": ["passed", "pending", "failed", "unknown"]},
    )


def conversation_case(index, rng):
    channel = rng.choice(["sms", "email", "phone"])
    old_channel = rng.choice([name for name in ["sms", "email", "phone"] if name != channel])
    day = rng.randrange(2, 23)
    deadline = f"2026-11-{day:02}"
    branch = index % 4
    approved, addressed, scheduled = branch in (1, 2), branch != 0, branch == 1
    events = [
        event(
            "old-preference",
            "user",
            f"Use {old_channel}. Deadline 2026-11-{day + 4:02}. Keep replies brief.",
        ),
        event("assistant-guess", "assistant", "I assume the delivery is approved and ready."),
        event(
            "current-preference",
            "user",
            f"Correction: use {channel}. Deadline {deadline}. "
            f"I {'approve' if approved else 'have not approved'} delivery. "
            f"My address {'is confirmed' if addressed else 'needs confirmation'}. "
            "Brief replies remain preferred.",
        ),
    ]
    if scheduled:
        events.append(
            event(
                "delivery-receipt",
                "tool",
                f"SIMULATED delivery scheduled for {deadline}, using the confirmed "
                f"address and approved request. Receipt D-{index:03}.",
            )
        )
    else:
        events.append(event("delivery-status", "tool", "No delivery has been scheduled."))
    events.append(event("distraction", "user", "Use a blue label if we print one."))
    pending = (
        "none"
        if scheduled
        else (
            "address_confirmation"
            if not addressed
            else ("schedule_delivery" if approved else "approval_confirmation")
        )
    )
    action = {
        "none": "declare_complete",
        "address_confirmation": "ask_address",
        "schedule_delivery": "schedule_delivery",
        "approval_confirmation": "ask_approval",
    }[pending]
    return QualificationCase(
        f"conversation-{index:03}",
        "conversation",
        events,
        ["current-preference", "delivery-receipt" if scheduled else "delivery-status"],
        "Report current contact method, deadline, user approval and unfinished prerequisite. "
        "Identify the next action. Complete means delivery was scheduled with approval "
        "and a confirmed address.",
        {
            "contact_method": channel,
            "deadline": deadline,
            "approved": str(approved).lower(),
            "pending": pending,
        },
        [] if scheduled else [action],
        ([] if scheduled else ["declare_complete"]) + ([] if approved else ["schedule_delivery"]),
        scheduled,
        ["delivery-receipt"] if scheduled else [],
        {
            "contact_method": ["sms", "email", "phone", "unknown"],
            "approved": ["true", "false", "unknown"],
            "pending": [
                "none",
                "address_confirmation",
                "approval_confirmation",
                "schedule_delivery",
                "unknown",
            ],
        },
    )


def budget_case(index, rng):
    names = ["pine", "oak", "cedar"]
    rng.shuffle(names)
    balances = {name: rng.randrange(10, 70) * 1000 for name in names}
    minimums = {name: rng.randrange(1, 7) * 1000 for name in names}
    if index % 4 == 3:
        balances[names[0]] = balances[names[1]]  # Exercise deterministic name tie-breaks.
    total = sum(minimums.values())
    budget = total + rng.randrange(1, 12) * 10000
    old_budget = budget + 20000
    payments = snowball_reference(balances, minimums, budget)
    target = min(balances, key=lambda name: (balances[name], name))
    executed = index % 4 == 2
    accounts = "; ".join(
        f"{name}: balance {balances[name]}, minimum {minimums[name]} cents" for name in names
    )
    events = [
        event(
            "accounts",
            "user",
            f"Synthetic one-month snowball; zero interest. {accounts}. "
            "Pay minimums first, then extra to smallest balance. Cap at balance and roll "
            "excess onward. Break equal-balance ties by ascending account name.",
        ),
        event("budget-old", "user", f"Total budget including minimums: {old_budget} cents."),
        event(
            "old-draft",
            "assistant",
            "A prior draft used the old budget. "
            "It does not establish current approval or execution.",
        ),
        event(
            "budget-current",
            "user",
            f"Correction: total budget is {budget} cents, including all minimums. "
            "Balances are unchanged.",
        ),
    ]
    if executed:
        events.append(
            event(
                "payment-receipt",
                "tool",
                "SIMULATED ledger: user approved the corrected budget and payments "
                f"were executed: {payments}. Receipt P-{index:03}.",
            )
        )
    else:
        events.append(
            event(
                "approval-status",
                "user",
                "No payments have been approved or executed. "
                "Return a revised draft and request approval before any payments.",
            )
        )
    events.append(event("distraction", "user", "Use green chart bars later."))
    return QualificationCase(
        f"budget-{index:03}",
        "budgeting",
        events,
        ["accounts", "budget-current", "payment-receipt" if executed else "approval-status"],
        "Report the current budget, sum of minimums, extra, smallest-balance target and "
        "each draft payment, in integer cents. Identify the next action after drafting. "
        "Complete means current payments were approved AND executed. "
        "Calculator results alone never prove execution.",
        {
            "budget_cents": str(budget),
            "minimums_cents": str(total),
            "extra_cents": str(budget - total),
            "target": target,
            **{f"{name}_payment_cents": str(value) for name, value in payments.items()},
        },
        [] if executed else ["request_approval"],
        ["execute_payments"] if executed else ["execute_payments", "declare_complete"],
        executed,
        ["payment-receipt"] if executed else [],
        {"target": ["pine", "oak", "cedar", "unknown"]},
        {"balances": balances, "minimums": minimums, "budget": budget},
    )


def generate_cases(config):
    factories = {
        "release_handoff": release_case,
        "conversation": conversation_case,
        "budgeting": budget_case,
    }
    cases = []
    for workflow in config.workflows:
        for index in range(config.cases_per_workflow):
            rng = random.Random(f"{config.seed}:{workflow}:{index}")
            cases.append(factories[workflow](index, rng))
    return cases


def answer_schema(case):
    schema = Continuation.model_json_schema()
    properties = {}
    for name in case.expected_facts:
        field = {"type": "string"}
        if name in case.categories:
            field["enum"] = case.categories[name]
        elif name.endswith("_cents"):
            field["pattern"] = r"^(unknown|[0-9]+)$"
        elif name == "deadline":
            field["pattern"] = r"^(unknown|[0-9]{4}-[0-9]{2}-[0-9]{2})$"
        elif name == "revision":
            field["enum"] = ["A", "B", "unknown"]
        properties[name] = field
    schema["properties"]["facts"] = {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
    schema["properties"]["next_actions"]["items"]["enum"] = [
        "update_implementation",
        "update_tests",
        "run_tests",
        "declare_complete",
        "ask_address",
        "ask_approval",
        "schedule_delivery",
        "request_approval",
        "execute_payments",
    ]
    return schema


def grade_qualification(case, answer):
    facts = {key: value.strip().lower() for key, value in answer.facts.items()}
    checks = {
        f"fact:{key}": facts.get(key) == value.lower() for key, value in case.expected_facts.items()
    }
    allowed_evidence = set(case.evidence_ids)
    if case.complete:
        allowed_evidence.update(case.minimal_ids)
        if case.workflow == "release_handoff" and case.expected_facts["revision"] == "A":
            allowed_evidence.add("requirement-A")
            # Redundant current recap, never a substitute for the required test-A.
            allowed_evidence.add("completion-A")
    cited = set(answer.evidence_ids)
    checks.update(
        {
            "required_actions": set(case.required_actions) <= set(answer.next_actions),
            "no_prohibited_actions": not set(case.prohibited_actions) & set(answer.next_actions),
            "completion_state": answer.complete == case.complete,
            "current_evidence": set(case.evidence_ids) <= cited <= allowed_evidence,
        }
    )
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "fact_accuracy": sum(checks[f"fact:{key}"] for key in case.expected_facts)
        / len(case.expected_facts),
    }
