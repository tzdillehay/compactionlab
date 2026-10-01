"""Export only reviewed synthetic fixture runs, retaining unsuccessful conditions."""

import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path
from statistics import median

from compactionlab.fixtures import load_case

ROOT = Path(__file__).resolve().parents[1]


def verify_synthetic(result):
    for case in result["cases"]:
        expected = [event.model_dump() for event in load_case(case["case"]).events]
        if case["history"] != expected:
            raise ValueError("Export refused: history differs from the public synthetic fixture")
    serialized = json.dumps(result)
    if any(marker in serialized for marker in ["/Users/", "gho_", "BEGIN PRIVATE KEY"]):
        raise ValueError("Export refused: potentially private data in run")
    if result["status"] != "completed":
        raise ValueError("Export refused: run is not complete")


def main():
    ids = json.loads((ROOT / ".local/smoke-run-ids.json").read_text())
    destination = ROOT / "results" / "smoke-2026-10-01"
    destination.mkdir(parents=True, exist_ok=True)
    runs, hashes = [], {}
    for identifier in ids:
        source = ROOT / ".local/runs" / f"{identifier}.json"
        run = json.loads(source.read_text())
        verify_synthetic(run)
        runs.append(run)
        shutil.copyfile(source, destination / source.name)
        hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    legacy = destination / "development"
    legacy.mkdir(exist_ok=True)
    for source in sorted((ROOT / ".local/runs").glob("*.json")):
        run = json.loads(source.read_text())
        if run["protocol"] in {"state-probe-v1", "state-probe-v2"}:
            verify_synthetic(run)
            shutil.copyfile(source, legacy / source.name)
            hashes[f"development/{source.name}"] = hashlib.sha256(source.read_bytes()).hexdigest()
    (destination / "manifest.json").write_text(
        json.dumps(
            {
                "protocol": "state-probe-v3",
                "run_ids": ids,
                "sha256": hashes,
                "hardware": {
                    "processor": "Apple M5 Pro",
                    "memory_gb": 24,
                    "model_backend": "Metal",
                },
                "scope": "Development smoke; byte ceilings; state probes; one repetition",
            },
            indent=2,
        )
        + "\n"
    )
    rows = [
        "# Local smoke results — October 1, 2026",
        "",
        "**Engineering smoke, not evidence of general memory-method superiority.**",
        "",
        "90 state probes: six configurations × three synthetic task templates × five methods. "
        "One repetition per configuration. All failures and unavailable conditions are retained. "
        "The same-model runs are controls. Compare methods within a fixed receiver and allowance.",
        "",
        "Hardware: Apple M5 Pro, 24 GB unified memory; Ollama 0.35.0, "
        "Qwen3 4B/8B Q4_K_M with thinking disabled. Runtime reported model weights fully in "
        "GPU memory. Model digests and every request/response are in the run JSON.",
        "",
        "## Strict passes and coverage",
        "",
        "Cells are passed/graded; `+Ne` means N unavailable/error trials. "
        "Each cell has 3 planned probes.",
        "",
        "| Writer → receiver | Historical bytes | Full | Recent | Summary | Plain | "
        "State + evidence |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    conditions = ["full_history", "recent_history", "summary", "plain", "structured"]
    for run in runs:
        cells = []
        for condition in conditions:
            total = run["totals"][condition]
            cell = f"{total['passed']}/{total['graded']}"
            if total["errors"]:
                cell += f" +{total['errors']}e"
            cells.append(cell)
        config = run["config"]
        rows.append(
            f"| {config['writer_model']} → {config['reader_model']} | "
            f"{config['byte_budget']} | {' | '.join(cells)} |"
        )
    rows += [
        "",
        "## Per-task outcomes",
        "",
        "Passes / graded, pooled here only as a coverage diagnostic across configurations; "
        "this is not a comparison that controls receiver capability.",
        "",
        "| Task | Full | Recent | Summary | Plain | State + evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in ["release_handoff", "conversation", "budgeting"]:
        cells = []
        for condition in conditions:
            trials = [
                trial
                for run in runs
                for trial in run["trials"]
                if trial["case"] == case and trial["condition"] == condition
            ]
            graded = [trial for trial in trials if trial["status"] == "graded"]
            cells.append(f"{sum(t['grade']['passed'] for t in graded)}/{len(graded)}")
        rows.append(f"| {case} | {' | '.join(cells)} |")
    rows += [
        "",
        "## Reader resource observations",
        "",
        "These mix warm/cold calls and different receivers; descriptive only. "
        "Writer cost is recorded separately in each case's summary_writer/memory_writer fields.",
        "",
        "| Method | Median wall seconds | Median reported load seconds | Median input tokens |",
        "| --- | ---: | ---: | ---: |",
    ]
    for condition in conditions:
        observations = [
            trial["model"]
            for run in runs
            for trial in run["trials"]
            if trial["condition"] == condition and trial["status"] == "graded"
        ]
        rows.append(
            f"| {condition} | {median(o['wall_seconds'] for o in observations):.3f} | "
            f"{median(o['load_seconds'] for o in observations):.3f} | "
            f"{median(o['prompt_tokens'] for o in observations):.0f} |"
        )
    failures = defaultdict(int)
    errors = []
    for run in runs:
        for trial in run["trials"]:
            if trial["status"] != "graded":
                errors.append(trial["error"])
            else:
                for check, passed in trial["grade"]["checks"].items():
                    if not passed:
                        failures[check] += 1
    rows += [
        "",
        "## What this establishes",
        "",
        "The service, real local inference, external memory transfer and independent grading "
        "run end to end. Structured records have not established an advantage in this pilot. "
        "Short histories produce ceiling effects, and the smaller receiver fails some "
        "full-history controls. Budgeting arithmetic/action failures also occur without "
        "compaction, so they cannot be attributed to memory alone. Model-written links and "
        "facts can be wrong; original source records make those errors inspectable.",
        "",
        "Next: qualify a capable receiver on independent tasks, add deterministic calculation "
        "tools equally to every condition, compare source-span preservation with free-text "
        "extraction, and add true tool continuations with token-matched context allowances.",
        "",
        "## Failed checks",
        "",
        "| Check | Count among graded probes |",
        "| --- | ---: |",
    ]
    for check, count in sorted(failures.items()):
        rows.append(f"| {check} | {count} |")
    rows += ["", "## Unavailable conditions", ""]
    rows += [f"- `{error}`" for error in sorted(set(errors))] or ["None."]
    rows += [
        "",
        "## Reproduce and inspect",
        "",
        "```sh",
        "uv sync --locked",
        "uv run python scripts/run_smoke.py",
        "uv run python scripts/export_smoke.py",
        "```",
        "",
        "Exact generations and timing may differ. Digests, seeds, settings, histories, "
        "memory proposals, rendered context, source-code hashes and raw responses are retained.",
        "",
        "## Runs",
        "",
    ]
    for run in runs:
        rows.append(f"- [{run['id']}]({run['id']}.json)")
    rows += [
        "",
        "Earlier v1/v2 contract-development runs are in [development](development/). "
        "They are not pooled with the frozen v3 matrix. [Manifest and hashes](manifest.json).",
        "",
    ]
    (destination / "README.md").write_text("\n".join(rows))
    print(destination)


if __name__ == "__main__":
    main()
