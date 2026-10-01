"""Independent behavior and evidence grading; never imported by retrieval."""


def grade(case, answer):
    facts = answer.facts.model_dump()
    fact_checks = {f"fact:{key}": facts[key] == value for key, value in case.expected_facts.items()}
    ready, proposed = set(case.ready_actions), set(answer.next_actions)
    completed = set(case.completed_actions)
    behavior = {
        **fact_checks,
        "required_actions": ready <= proposed,
        "no_extra_actions": proposed <= ready,
        "no_repeated_completed_actions": not proposed & completed,
        "completed_actions": set(answer.completed_actions) == completed,
        "honest_completion": answer.complete == case.complete,
    }
    evidence = {
        "fact_provenance": set(case.fact_ids)
        <= set(answer.fact_source_ids)
        <= set(case.minimal_ids),
        "completion_evidence": set(answer.completion_evidence_ids) == set(case.completion_ids),
    }
    checks = {**behavior, **evidence}
    return {
        "passed": all(checks.values()),
        "behavior_passed": all(behavior.values()),
        "checks": checks,
        "fact_accuracy": sum(fact_checks.values()) / len(fact_checks),
        "missed_actions": sorted(ready - proposed),
        "extra_actions": sorted(proposed - ready),
        "repeated_actions": sorted(proposed & completed),
        "false_completion": answer.complete and not case.complete,
    }
