"""Export every outcome of the fixed synthetic encoding sweep; never select winners."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from statistics import median

from export_smoke import verify_synthetic

from compactionlab.representation import CONDITIONS, load_frozen, summarize

ROOT = Path(__file__).resolve().parents[1]


def passed(row):
    return row["status"] == "graded" and row["grade"]["passed"]


def measurement(observations, field, fmt="g"):
    values = [o[field] for o in observations if isinstance(o.get(field), (int, float))]
    return format(median(values), fmt) if values else "unavailable"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--hardware-note", default="Hardware details unspecified")
    args = parser.parse_args()
    if len(args.run_id) != 12 or any(c not in "0123456789abcdef" for c in args.run_id):
        raise ValueError("Use the saved twelve-character hexadecimal run ID")
    if len(args.source_commit) != 40 or any(
        c not in "0123456789abcdef" for c in args.source_commit
    ):
        raise ValueError("Provide a full frozen source commit SHA")
    path = ROOT / ".local/runs" / f"{args.run_id}.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    verify_synthetic(result)
    if result["protocol"] != "representation-v1":
        raise ValueError("Export requires a completed representation-v1 replay")
    frozen = load_frozen(ROOT / "results/token-budget-2026-10-01/1b62ebbc316d.json")
    originals = {row["case"]: row for row in frozen["cases"]}
    for row in result["cases"]:
        if row["records"] != originals[row["case"]]["memory_writer"]["parsed"]["records"]:
            raise ValueError("Frozen writer records changed")
    for name, digest in result["source_sha256"].items():
        raw = subprocess.check_output(
            ["git", "show", f"{args.source_commit}:src/compactionlab/{name}"], cwd=ROOT
        )
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"Source commit does not match recorded {name}")
    config = result["config"]
    expected = {
        (case, seed, budget, condition)
        for case in originals
        for seed in config["seeds"]
        for budget in config["budgets"]
        for condition in CONDITIONS
    } | {(case, seed, None, "full_history") for case in originals for seed in config["seeds"]}
    index = {(t["case"], t["seed"], t["token_budget"], t["condition"]): t for t in result["trials"]}
    if set(index) != expected or len(index) != len(result["trials"]):
        raise ValueError("Missing or duplicated planned trials; retain every outcome")
    if result["totals"] != summarize(result["trials"]):
        raise ValueError("Saved aggregate is inconsistent")
    destination = ROOT / "results/representation-2026-10-01"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination / path.name)
    manifest = {
        "protocol": result["protocol"],
        "run_ids": [args.run_id],
        "source_commit": args.source_commit,
        "sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()},
        "frozen_source": result["frozen_source"],
        "hardware_note": args.hardware_note,
        "scope": "Development encoding ablation of three known checkpoints; seeds are repeats",
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Frozen memory encoding results — October 1, 2026",
        "",
        f"**{len(result['trials'])} planned receiving calls, with every outcome retained.** "
        "This is a development ablation of three known checkpoints, not held-out evaluation. "
        f"Qwen3 4B's frozen writer output goes to {config['reader_model']} with reasoning "
        f"{'enabled' if config['reader_settings']['thinking'] else 'disabled'}. "
        "No memory content, writer links, reader prompt or grading was repaired "
        "between conditions.",
        "",
        f"Hardware note: {args.hardware_note}. Recorded platform: {result['hardware']}. "
        "Model/runtime/tokenizer manifests and exact sampling settings are in the trace. "
        "Input is preflighted with output reserve, and complete rendered-input counts are audited.",
        "",
        "## Strict recall",
        "",
        "Cells are passes / planned, including errors as failures. Each bounded cell repeats "
        f"one task with {len(config['seeds'])} seeds. Full references have the same seed count "
        "per workflow and are repeated "
        "in the table for comparison. They are not new qualification results.",
        "",
        "| Workflow | Historical tokens | Verbose | Compact | Compact fixed selection | "
        "Recent | Full reference |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in originals:
        for budget in config["budgets"]:
            cells = []
            for condition in (*CONDITIONS, "full_history"):
                rows = [
                    index[(case, seed, None if condition == "full_history" else budget, condition)]
                    for seed in config["seeds"]
                ]
                cells.append(f"{sum(passed(row) for row in rows)}/{len(rows)}")
            lines.append(f"| {case} | {budget} | {' | '.join(cells)} |")
    lines += [
        "",
        "## Fact recall, separate from complete-task passes",
        "",
        "Cells are mean correct fact fields across seeds. They exclude action, completion and "
        "evidence checks, so factual gains can coexist with complete-task failures. "
        "The budget workflow failed every fresh full-history reference and remains diagnostic.",
        "",
        "| Workflow | Historical tokens | Verbose | Compact | Fixed selection | Recent |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in originals:
        for budget in config["budgets"]:
            cells = []
            for condition in CONDITIONS:
                rows = [index[(case, seed, budget, condition)] for seed in config["seeds"]]
                graded = [row for row in rows if row["status"] == "graded"]
                accuracy = (
                    sum(row["grade"]["fact_accuracy"] for row in graded) / len(graded)
                    if graded
                    else None
                )
                cells.append(f"{accuracy:.1%}" if accuracy is not None else "unavailable")
            lines.append(f"| {case} | {budget} | {' | '.join(cells)} |")
    lines += [
        "",
        "## Paired changes from verbose encoding",
        "",
        "A win is a failure becoming a strict pass on the same case, allowance and seed; "
        "a regression is a pass becoming a failure. These repeats are not independent tasks.",
        "",
        "| Condition | Wins | Regressions | Same pass/fail |",
        "| --- | ---: | ---: | ---: |",
    ]
    for condition in ("compact", "compact_fixed", "recent_history"):
        pairs = [
            (row, index[(*key[:3], condition)])
            for key, row in index.items()
            if key[3] == "structured"
        ]
        wins = sum(not passed(a) and passed(b) for a, b in pairs)
        losses = sum(passed(a) and not passed(b) for a, b in pairs)
        lines.append(f"| {condition} | {wins} | {losses} | {len(pairs) - wins - losses} |")
    lines += [
        "",
        "## Packet coverage and resource observations",
        "",
        "The encoding-only control preserves exactly the verbose selection. Adaptive compact "
        "selection may admit different records, including stale or irrelevant ones. "
        "Selection and token size do not imply accurate recall.",
        "",
        "| Workflow | Allowance | Verbose records / tokens | Compact records / tokens | "
        "Fixed compact tokens |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for case in originals:
        for budget in config["budgets"]:
            a, b, c = [
                index[(case, config["seeds"][0], budget, condition)]
                for condition in ("structured", "compact", "compact_fixed")
            ]
            lines.append(
                f"| {case} | {budget} | {len(a['retrieval']['record_ids'])} / "
                f"{a['historical_tokens']} | {len(b['retrieval']['record_ids'])} / "
                f"{b['historical_tokens']} | {c['historical_tokens']} |"
            )
    observations = [t["model"] for t in result["trials"] if "model" in t]
    errors = sum(t["status"] != "graded" for t in result["trials"])
    audited = [o for o in observations if o.get("prompt_tokens") is not None]
    matches = sum(o.get("prompt_accounting_match") is True for o in audited)
    lines += [
        "",
        f"{errors} retained errors. Rendered-input token audits matched on "
        f"{matches}/{len(audited)} calls with reported input counts. "
        "Lossless packet reconstruction passed before inference. Original 128-token baseline "
        f"parity: {result['baseline_parity']} (null means a different tokenizer). "
        "Packet construction runs once per case/budget/encoding; its "
        "saved timing is reused across seeds, not independent latency samples.",
        "",
        "| Condition | Median receiving wall seconds | Median input tokens | "
        "Median output tokens |",
        "| --- | ---: | ---: | ---: |",
    ]
    for condition in ("full_history", *CONDITIONS):
        obs = [t["model"] for t in result["trials"] if t["condition"] == condition and "model" in t]
        lines.append(
            f"| {condition} | {measurement(obs, 'wall_seconds', '.3f')} | "
            f"{measurement(obs, 'prompt_tokens')} | {measurement(obs, 'output_tokens')} |"
        )
    lines += [
        "",
        "Descriptive timings mix warm/cold calls and different packet lengths and output "
        "content; they do not establish a speed advantage. Writer extraction cost was paid "
        "in the previous frozen source run, not repeated or included in these timings. "
        "These short source histories can fit within some allowances while their extracted "
        "graphs cannot. Compare recent history before claiming an advantage from external memory.",
        "",
        "The original unaided budget problem is diagnostic when its full-history control "
        "fails; different calculator-aided qualification tasks do not qualify it. "
        "Any improvements or regressions here need replication on new tasks and other model "
        "families before broader claims.",
        "",
        "## Reproduce",
        "",
        "```sh",
        "uv sync --locked",
        "uv run compactionlab prepare-tokenizer --model qwen3:8b",
        "uv run compactionlab replay --source results/token-budget-2026-10-01/1b62ebbc316d.json "
        "--budgets 128 256 384 512 --seeds 42 43 44",
        "uv run python scripts/export_representation.py SAVED_RUN_ID "
        f"--source-commit {args.source_commit}",
        "```",
        "",
        f"[Frozen source](https://github.com/tzdillehay/compactionlab/tree/{args.source_commit}) · "
        f"[Raw trace]({path.name}) · [Integrity manifest](manifest.json) · "
        "[Protocol](../../docs/representation.md)",
        "",
    ]
    (destination / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
