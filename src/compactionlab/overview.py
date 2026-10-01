"""Read-only study inventory. Coverage metrics are not a ranking across protocols."""

import json
import re
from pathlib import Path
from statistics import mean, median

STUDIES = {
    "lifecycle": (
        "Task-state retrieval",
        "Current facts, completed actions, and pending follow-ups",
    ),
    "bytes": ("Byte-budget comparisons", "Full, recent, summary, plain, and structured memory"),
    "qualification": ("Receiver qualification", "Full history and annotated source controls"),
    "tokens": (
        "Token-budget stress",
        "Enforce historical-token allowances before comparing recall",
    ),
    "encoding": (
        "Compact encoding",
        "Frozen memory, shared sources, and a fixed-selection control",
    ),
}


def catalog(data_dir: Path, published_dir: Path | None = None):
    """Merge shipped evidence and local results once per ID; local progress takes precedence."""
    entries = {}
    if published_dir and published_dir.is_dir():
        for path in sorted(published_dir.rglob("*.json")):
            if re.fullmatch(r"[a-f0-9]{12}", path.stem):
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get("id") == path.stem:
                    entries[path.stem] = {
                        "result": value,
                        "published": True,
                        "kind": "qualification"
                        if value.get("protocol", "").startswith("qualification-")
                        else "comparison",
                    }
    for folder in ("runs", "qualifications"):
        for path in sorted((data_dir / folder).glob("*.json")):
            if re.fullmatch(r"[a-f0-9]{12}", path.stem):
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get("id") == path.stem:
                    entries[path.stem] = {
                        "result": value,
                        "published": entries.get(path.stem, {}).get("published", False)
                        and value == entries[path.stem]["result"],
                        "kind": "qualification" if folder == "qualifications" else "comparison",
                    }
    return sorted(
        entries.values(),
        key=lambda e: (e["result"].get("created_at", ""), e["result"]["id"]),
        reverse=True,
    )


def metrics(trials):
    graded = [t for t in trials if t.get("status") == "graded" and t.get("grade")]
    times = [t["model"]["wall_seconds"] for t in trials if "wall_seconds" in (t.get("model") or {})]
    facts = [t["grade"]["fact_accuracy"] for t in graded if "fact_accuracy" in t["grade"]]
    return {
        "saved": len(trials),
        "graded": len(graded),
        "passed": sum(bool(t["grade"].get("passed")) for t in graded),
        "errors": len(trials) - len(graded),
        "mean_fact_accuracy": mean(facts) if facts else None,
        "median_receiver_seconds": median(times) if times else None,
        "timed_responses": len(times),
    }


def study_key(result):
    protocol = result.get("protocol", "unknown")
    if protocol in {"state-probe-v1", "state-probe-v2", "qualification-v1", "qualification-v2"}:
        return "development"
    if protocol == "qualification-v3":
        return "qualification"
    if protocol in {"state-probe-v3", "state-probe-v4"}:
        return "tokens" if result["config"].get("token_budget") is not None else "bytes"
    if protocol == "lifecycle-v1":
        return "lifecycle"
    if protocol == "representation-v1":
        return "encoding"
    return protocol


def run_summary(entry):
    result = entry["result"]
    config = result["config"]
    qualification = entry["kind"] == "qualification"
    reader = config.get("model") or config.get("reader_model")
    writer = config.get("writer_model") or result.get("frozen_writer", {}).get("name")
    models = sorted({name for name in (reader, writer) if name})
    thinking = config.get("settings" if qualification else "reader_settings", {}).get("thinking")
    allowances = (
        f"{', '.join(map(str, config['budgets']))} tokens"
        if "budgets" in config
        else f"{config['token_budget']:,} tokens"
        if config.get("token_budget") is not None
        else f"{config.get('byte_budget', 0):,} bytes"
    )
    origin = writer or (
        "Typed API memory" if result.get("memory_origin") == "typed_api_events" else "Frozen memory"
    )
    setup = (
        f"{reader} · reasoning {'on' if thinking else 'off'}"
        if qualification
        else f"{origin} → {reader} · {allowances}"
    )
    summary = {
        "id": result["id"],
        "created_at": result.get("created_at"),
        "status": result.get("status"),
        "protocol": result.get("protocol", "unknown"),
        "kind": "qualification" if qualification else "comparison",
        "published": entry["published"],
        "models": models,
        "setup": setup,
        "metrics": metrics(result.get("trials", [])),
    }
    if result.get("protocol") == "lifecycle-v1":
        summary["lifecycle"] = {
            "supported": len(result.get("analysis", {}).get("control_supported_cases", [])),
            "cases": len(result.get("cases", [])),
            "totals": result.get("totals", {}),
            "parity": result.get("analysis", {}).get("packet_parity"),
        }
    if qualification:
        summary["workflow_gates"] = {
            workflow: bool(total.get("qualified"))
            for workflow, total in result.get("totals", {}).items()
        }
    if result.get("protocol") == "representation-v1":
        paired = {}
        for trial in result.get("trials", []):
            key = (trial["case"], trial["seed"], trial.get("token_budget"))
            paired.setdefault(key, {})[trial["condition"]] = trial
        pairs = [p for p in paired.values() if {"structured", "compact"} <= p.keys()]
        changes = [
            int(bool(p["compact"].get("grade", {}).get("passed")))
            - int(bool(p["structured"].get("grade", {}).get("passed")))
            for p in pairs
        ]
        reductions = [
            1 - p["compact_fixed"]["historical_tokens"] / p["structured"]["historical_tokens"]
            for p in paired.values()
            if {"structured", "compact_fixed"} <= p.keys()
            and p["structured"].get("historical_tokens", 0) > 0
            and p["compact_fixed"].get("fidelity_verified") is True
        ]
        summary["encoding"] = {
            "pairs": len(changes),
            "wins": changes.count(1),
            "losses": changes.count(-1),
            "ties": changes.count(0),
            "same_selection_token_reduction": [min(reductions), max(reductions)]
            if reductions
            else None,
        }
    return summary


def overview(entries):
    studies = {}
    development = []
    all_trials = []
    models = set()
    workflows = set()
    for entry in entries:
        result = entry["result"]
        summary = run_summary(entry)
        trials = result.get("trials", [])
        all_trials.extend(trials)
        models.update(summary["models"])
        workflows.update(t.get("workflow") or t.get("case", "unknown") for t in trials)
        key = study_key(result)
        if key == "development":
            development.append(summary)
            continue
        if key not in studies:
            title, description = STUDIES.get(key, (key, "Additional saved protocol"))
            studies[key] = {
                "id": key,
                "title": title,
                "description": description,
                "runs": [],
                "trials": [],
            }
        studies[key]["runs"].append(summary)
        studies[key]["trials"].extend(trials)
    for study in studies.values():
        study["metrics"] = metrics(study.pop("trials"))
        study["protocols"] = sorted({r["protocol"] for r in study["runs"]})
    ordered = sorted(
        studies.values(), key=lambda s: list(STUDIES).index(s["id"]) if s["id"] in STUDIES else 99
    )
    return {
        "summary": {
            "studies": len(studies),
            "runs": len(entries),
            "completed_runs": sum(e["result"].get("status") == "completed" for e in entries),
            "saved_probes": len(all_trials),
            "models": sorted(models),
            "workflows": sorted(workflows),
            "development_runs": len(development),
            "latest_at": max((e["result"].get("created_at", "") for e in entries), default=None),
        },
        "studies": ordered,
        "development": development,
    }
