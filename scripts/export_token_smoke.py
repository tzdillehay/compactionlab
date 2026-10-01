"""Publish one completed synthetic token-accounting smoke, including failures."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from statistics import median

from export_smoke import verify_synthetic

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    args = parser.parse_args()
    if len(args.run_id) != 12 or any(c not in "0123456789abcdef" for c in args.run_id):
        raise ValueError("Use the saved twelve-character hexadecimal run ID")
    source = ROOT / ".local/runs" / f"{args.run_id}.json"
    result = json.loads(source.read_text(encoding="utf-8"))
    verify_synthetic(result)
    if result["protocol"] != "state-probe-v4" or result["config"]["token_budget"] is None:
        raise ValueError("A completed token-accounted V4 run is required")
    destination = ROOT / "results/token-budget-2026-10-01"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination / source.name)
    manifest = {
        "protocol": "state-probe-v4",
        "run_ids": [args.run_id],
        "sha256": {source.name: hashlib.sha256(source.read_bytes()).hexdigest()},
        "scope": "Engineering smoke of token allowance enforcement, not a method comparison",
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    budget = result["config"]["token_budget"]
    lines = [
        "# Historical-token accounting smoke — October 1, 2026",
        "",
        f"{len(result['cases'])} short synthetic checkpoints, five conditions, "
        f"{len(result['trials'])} planned probes, {budget} historical tokens. "
        f"Writer: {result['config']['writer_model']}; "
        f"receiver: {result['config']['reader_model']}. "
        "Inference settings and repetitions are recorded in the trace. "
        "This tests budget enforcement through the actual local service and dashboard. "
        "It is separate from the receiver qualification and original byte-budget smoke. "
        "It uses the original fixtures without a calculator observation; "
        "qualification on the aided parameterized tasks does not qualify these different tasks.",
        "",
        "The allowance counts the escaped JSON string value inserted as historical_context, "
        "including metadata. Full history is an unbounded reference. "
        "Recent history keeps complete events; record retrieval keeps complete dependency groups; "
        "an over-budget summary becomes a retained writer error. "
        "The summary writer still uses the original 1400-character instruction; "
        "it is not trained or prompted to optimize this token allowance.",
        "",
        "| Method | Passes / planned | Graded | Errors | Largest bounded history tokens |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for condition, total in result["totals"].items():
        sizes = [
            t["historical_tokens"]
            for t in result["trials"]
            if t["condition"] == condition and "context" in t
        ]
        largest = str(max(sizes)) if sizes else "unavailable"
        if condition == "full_history":
            largest += " (unbounded reference)"
        lines.append(
            f"| {condition} | {total['passed']}/{total['planned']} | "
            f"{total['graded']} | {total['errors']} | {largest} |"
        )
    observations = [t["model"] for t in result["trials"] if "model" in t]
    matches = sum(o.get("prompt_accounting_match") is True for o in observations)
    retrievals = [t["retrieval_seconds"] for t in result["trials"] if "retrieval_seconds" in t]
    retrieval_note = (
        f"Median measured record-retrieval time: {median(retrievals) * 1000:.3f} ms "
        f"over {len(retrievals)} tiny-store calls, including token budget checks. "
        "This excludes model inference and network/client overhead and is not a scale benchmark."
        if retrievals
        else "Record-retrieval timing was unavailable."
    )
    lines += [
        "",
        f"Full rendered-input token audits matched on {matches}/{len(observations)} reader calls. "
        "Runtime costs and all unavailable conditions are retained in the raw trace. "
        "Input/output costs, extraction costs, and retrieval timing are separate from the "
        "historical allowance. This does not establish a recall-speed or accuracy improvement.",
        "",
        retrieval_note,
        "",
        "## Reproduce",
        "",
        "```sh",
        "uv sync --locked",
        "uv run compactionlab prepare-tokenizer --model qwen3:8b",
        "uv run compactionlab evaluate --writer qwen3:4b --reader qwen3:8b "
        f"--token-budget {budget}",
        "uv run python scripts/export_token_smoke.py SAVED_RUN_ID",
        "```",
        "",
        f"[Raw trace]({source.name}) · [Integrity manifest](manifest.json) · "
        "[Token protocol](../../docs/qualification.md)",
        "",
    ]
    (destination / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
