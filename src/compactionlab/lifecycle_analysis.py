"""Paired descriptive comparisons; retain errors and unsupported control cases."""


def analyze(trials):
    by_case = {}
    for trial in trials:
        by_case.setdefault(trial["case"], {})[trial["condition"]] = trial

    def passes(trial, metric):
        return trial.get("status") == "graded" and bool(trial.get("grade", {}).get(metric))

    supported = [
        case
        for case, methods in by_case.items()
        if all(
            passes(methods.get(control, {}), "behavior_passed")
            for control in ("full_history", "minimal_source")
        )
    ]

    def pairs(identifiers, baseline, metric):
        values = [
            int(passes(by_case[case]["linked_current"], metric))
            - int(passes(by_case[case][baseline], metric))
            for case in identifiers
            if {"linked_current", baseline} <= by_case[case].keys()
        ]
        return {
            "pairs": len(values),
            "wins": values.count(1),
            "losses": values.count(-1),
            "ties": values.count(0),
        }

    result = {
        "control_supported_cases": supported,
        "control_excluded_cases": sorted(set(by_case) - set(supported)),
        "paired": {},
        "packet_parity": {},
        "breakdowns": {},
    }
    for scope, identifiers in (("all", list(by_case)), ("control_supported", supported)):
        result["paired"][scope] = {
            baseline: {
                metric: pairs(identifiers, baseline, metric)
                for metric in ("behavior_passed", "passed")
            }
            for baseline in ("lexical", "recent_history", "summary", "current_no_links")
        }
    ablations = [m for m in by_case.values() if {"current_no_links", "linked_current"} <= m.keys()]
    result["packet_parity"] = {
        "pairs": len(ablations),
        "identical": sum(
            m["current_no_links"].get("context") == m["linked_current"].get("context")
            for m in ablations
        ),
    }
    for dimension in ("workflow", "checkpoint", "placement"):
        groups = {}
        for trial in trials:
            group = groups.setdefault(trial[dimension], {})
            rows = group.setdefault(
                trial["condition"], {"saved": 0, "behavior_passed": 0, "passed": 0}
            )
            rows["saved"] += 1
            for metric in ("behavior_passed", "passed"):
                rows[metric] += passes(trial, metric)
        result["breakdowns"][dimension] = groups
    return result
