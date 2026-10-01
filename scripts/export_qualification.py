"""Export synthetic capability traces without dropping unsuccessful outcomes."""

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from statistics import median

from compactionlab.qualification_cases import generate_cases
from compactionlab.schemas import QualificationRequest

ROOT = Path(__file__).resolve().parents[1]


def verify(result):
    if result["status"] != "completed":
        raise ValueError("Only completed studies can be exported")
    cases = generate_cases(QualificationRequest.model_validate(result["config"]))
    expected = {case.id: [event.model_dump() for event in case.events] for case in cases}
    if len(result["cases"]) != len(expected):
        raise ValueError("Case coverage differs from the synthetic generator")
    for case in result["cases"]:
        if case["events"] != expected[case["id"]]:
            raise ValueError("Export refused: source history is not the synthetic fixture")
    serialized = json.dumps(result)
    if any(marker in serialized for marker in ["/Users/", "gho_", "BEGIN PRIVATE KEY"]):
        raise ValueError("Export refused: potentially private data")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hardware-note", default="Additional processor, memory and GPU details not recorded."
    )
    args = parser.parse_args()
    ids = json.loads((ROOT / ".local/qualification-study-ids.json").read_text(encoding="utf-8"))
    if len(ids) != 2:
        raise ValueError("Both frozen inference configurations must be complete")
    destination = ROOT / "results/qualification-2026-10-01"
    destination.mkdir(parents=True, exist_ok=True)
    runs, hashes = [], {}
    for identifier in ids:
        source = ROOT / ".local/qualifications" / f"{identifier}.json"
        result = json.loads(source.read_text(encoding="utf-8"))
        verify(result)
        if result["protocol"] != "qualification-v3":
            raise ValueError("Unexpected qualification protocol")
        runs.append(result)
        shutil.copyfile(source, destination / source.name)
        hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    if runs[0]["source_sha256"] != runs[1]["source_sha256"]:
        raise ValueError("Core implementation changed between frozen configurations")
    paired_configs = [{k: v for k, v in r["config"].items() if k != "settings"} for r in runs]
    if paired_configs[0] != paired_configs[1] or runs[0]["tokenizer"] != runs[1]["tokenizer"]:
        raise ValueError("Paired fixtures or model/tokenizer identity changed")
    development = destination / "development"
    development.mkdir(exist_ok=True)
    for source in (ROOT / ".local/qualifications").glob("*.json"):
        result = json.loads(source.read_text(encoding="utf-8"))
        if result["protocol"] in {"qualification-v1", "qualification-v2"}:
            verify(result)
            shutil.copyfile(source, development / source.name)
            hashes[f"development/{source.name}"] = hashlib.sha256(source.read_bytes()).hexdigest()
    metadata = {
        "protocol": "qualification-v3",
        "run_ids": ids,
        "sha256": hashes,
        "hardware": [r["hardware"] for r in runs],
        "hardware_note": args.hardware_note,
        "scope": "Parameterized capability calibration, not autonomous execution",
    }
    (destination / "manifest.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Receiver qualification — October 1, 2026",
        "",
        f"{sum(len(r['trials']) for r in runs)} probes: "
        f"{len(runs[0]['cases'])} parameterized cases × two source conditions "
        "× two inference configurations. "
        "The same Qwen3 8B Q4_K_M digest and fixture instances are used in both configurations. "
        "Every planned outcome, failure and raw response is retained. This is a development "
        "capability screen, not evidence of memory-method superiority or autonomous competence.",
        "",
        f"Recorded platform: {runs[0]['hardware']['system']} / "
        f"{runs[0]['hardware']['machine']}; Ollama {runs[0]['model']['ollama_version']}. "
        f"{args.hardware_note}",
        "",
        "## Full-history qualification",
        "",
        "At least 20 full-history cases and 90% strict success per workflow are required. "
        "Errors count as failures. Minimal sources are an annotated diagnostic subset, "
        "not a learned memory policy.",
        "",
        "| Thinking | Workflow | Full passes / planned | Minimal passes / planned | "
        "Full errors | Gate |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for run in runs:
        for workflow, total in run["totals"].items():
            full, minimal = total["full_history"], total["minimal_source"]
            lines.append(
                f"| {run['config']['settings']['thinking']} | {workflow} | "
                f"{full['passed']}/{full['planned']} | {minimal['passed']}/{minimal['planned']} | "
                f"{full['errors']} | {'qualified' if total['qualified'] else 'not qualified'} |"
            )
    lines += [
        "",
        "## What failed",
        "",
        "Strict success includes the completion-only evidence contract. Citing a correct source "
        "for an unfinished task still fails that contract, which requires an empty evidence list. "
        "The components below separate this instruction-following failure from wrong facts or "
        "completion state. Counts use all planned full-history trials; "
        "errors fail every component. "
        "These diagnostics do not replace the frozen operational gate.",
        "",
        "| Thinking | Workflow | All facts correct | Action checks met | Completion correct | "
        "Evidence contract met |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        for workflow in run["config"]["workflows"]:
            rows = [
                t
                for t in run["trials"]
                if t["workflow"] == workflow and t["condition"] == "full_history"
            ]
            checks = [t["grade"]["checks"] for t in rows if t["status"] == "graded"]
            counts = [
                sum(all(v for k, v in c.items() if k.startswith("fact:")) for c in checks),
                sum(c["required_actions"] and c["no_prohibited_actions"] for c in checks),
                sum(c["completion_state"] for c in checks),
                sum(c["current_evidence"] for c in checks),
            ]
            cells = " | ".join(f"{count}/{len(rows)}" for count in counts)
            lines.append(f"| {run['config']['settings']['thinking']} | {workflow} | {cells} |")
    lines += [
        "",
        "## Resource observations",
        "",
        "Both modes use 8192 context tokens. Non-thinking uses a 2048-token output allowance, "
        "temperature 0.7 and top-p 0.8; thinking uses 6144, 0.6 and 0.95. "
        "This compares inference configurations, not thinking alone. Cold/warm loading is retained "
        "per call, so these mixed-call medians are descriptive. "
        "The non-thinking run precedes the thinking run; configuration order is not randomized.",
        "",
        "| Thinking | Median wall seconds | Median input tokens | Median output tokens | "
        "Token audits matching |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        observations = [t["model"] for t in run["trials"] if "prompt_tokens" in t.get("model", {})]
        values = (
            [
                f"{median(o['wall_seconds'] for o in observations):.3f}",
                f"{median(o['prompt_tokens'] for o in observations):.0f}",
                f"{median(o['output_tokens'] for o in observations):.0f}",
            ]
            if observations
            else ["unavailable"] * 3
        )
        lines.append(
            f"| {run['config']['settings']['thinking']} | " + " | ".join(values) + " | "
            f"{sum(o['prompt_accounting_match'] is True for o in observations)}"
            f"/{len(observations)} |"
        )
    lines += ["", "## Failed checks", "", "| Thinking | Check | Count |", "| --- | --- | ---: |"]
    for run in runs:
        failures = Counter(
            k
            for t in run["trials"]
            if t["status"] == "graded"
            for k, ok in t["grade"]["checks"].items()
            if not ok
        )
        for check, count in sorted(failures.items()):
            lines.append(f"| {run['config']['settings']['thinking']} | {check} | {count} |")
    lines += [
        "",
        "## Interpretation and boundaries",
        "",
        "The receiver reports current facts, actions, completion and evidence. "
        "Shipping observations "
        "come from actual fixture assertions; deliveries and payment receipts are simulated. "
        "A deterministic calculator receives visible fixture inputs and supplies "
        "a draft to both conditions. "
        "This does not test model-driven tool selection or real-world actions.",
        "",
        "Qualification applies only to these shared-template state probes. "
        "Twenty parameterized cases "
        "are an operational screen, not broad generalization evidence. No memory-method comparison "
        "is made here. A passing full-history gate does not imply that minimal sources, "
        "long histories, "
        "or actual agent continuations will succeed.",
        "",
        "The calibrated historical unit includes JSON escaping. Full prompt rendering is audited "
        "against Ollama on every call. Tokenizer revision, SHA-256, model digest and template hash "
        "are included in each trace. Raw reasoning and output-length failures are retained.",
        "",
        "V1/V2 development traces and their original grades are retained separately "
        "in [development](development/). "
        "Their evidence-contract corrections are described in the "
        "[protocol](../../docs/qualification.md). "
        "They are not pooled with V3 or the original smoke report.",
        "",
        "## Reproduce",
        "",
        "```sh",
        "uv sync --locked",
        "uv run compactionlab prepare-tokenizer --model qwen3:8b",
        "uv run python scripts/run_qualification_study.py",
        "uv run python scripts/export_qualification.py",
        "```",
        "",
        "Generations and timings may vary. [Manifest and integrity hashes](manifest.json).",
        "",
        "## Runs",
        "",
    ]
    lines += [f"- [{run['id']}]({run['id']}.json)" for run in runs]
    lines.append("")
    (destination / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
