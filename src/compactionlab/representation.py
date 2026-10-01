"""Paired encoding ablation of one frozen, public model-written memory graph."""

import hashlib
import json
import platform
import random
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from filelock import FileLock, Timeout

from compactionlab import __version__
from compactionlab.experiment import (
    ACTION_DESCRIPTIONS,
    READER_SYSTEM,
    bounded_events,
    continuation_schema,
)
from compactionlab.fixtures import load_case
from compactionlab.grading import grade
from compactionlab.ollama import ModelFailure
from compactionlab.packets import compact_packet, expand_packet
from compactionlab.schemas import ContextRequest, Continuation, MemoryExtraction, WriteBatch
from compactionlab.tokens import load_counter

FROZEN_SHA256 = "c50231360180c09de5aee8a175a741e427b55793406ce2d16ff751dd2ab3cc13"
CONDITIONS = ("structured", "compact", "compact_fixed", "recent_history")


def load_frozen(source: Path) -> dict:
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_SHA256:
        raise ValueError("Replay requires the exact published synthetic 1b62ebbc316d trace")
    result = json.loads(raw)
    for row in result["cases"]:
        if row["history"] != [event.model_dump() for event in load_case(row["case"]).events]:
            raise ValueError("Frozen source differs from the checked-in synthetic fixture")
        MemoryExtraction.model_validate(row["memory_writer"]["parsed"])
    return result


def seed_graph(store, namespace, row):
    case = load_case(row["case"])
    extraction = MemoryExtraction.model_validate(row["memory_writer"]["parsed"])
    store.write(namespace, WriteBatch(expected_revision=0, events=case.events))
    store.write(namespace, WriteBatch(expected_revision=1, records=extraction.records))


def packets(store, namespace, case, budget, counter):
    """No answers or grade annotations participate in ranking or packet construction."""
    values = {}
    for mode in ("structured", "compact"):
        start = time.perf_counter()
        retrieval = store.context(
            namespace,
            ContextRequest(query=case.request, mode=mode),
            token_budget=budget,
            counter=counter,
        )
        values[mode] = {
            "context": retrieval["text"],
            "retrieval": retrieval,
            "retrieval_seconds": round(time.perf_counter() - start, 6),
        }
    snapshot = store.snapshot(namespace)
    verbose = json.loads(values["structured"]["context"])
    fixed = compact_packet(verbose, snapshot["events"])
    if expand_packet(fixed) != verbose:
        raise ValueError("Compact fixed-selection packet failed lossless reconstruction")
    values["compact_fixed"] = {
        "context": fixed,
        "record_ids": values["structured"]["retrieval"]["record_ids"],
        "fidelity_verified": True,
    }
    values["recent_history"] = {
        "context": bounded_events(snapshot["events"], budget, recent=True, counter=counter)
    }
    compact_units = expand_packet(values["compact"]["context"])
    by_id = {record["id"]: record for record in snapshot["records"]}
    for unit in compact_units:
        original = {k: v for k, v in by_id[unit["id"]].items() if k != "seq"}
        original["sources"] = [
            event for event in snapshot["events"] if event["id"] in original["source_ids"]
        ]
        if unit != original:
            raise ValueError("Compact selected packet failed lossless reconstruction")
    values["compact"]["fidelity_verified"] = True
    return values


def summarize(trials):
    totals = {}
    for condition in ("full_history", *CONDITIONS):
        rows = [row for row in trials if row["condition"] == condition]
        graded = [row for row in rows if row["status"] == "graded"]
        totals[condition] = {
            "planned": len(rows),
            "graded": len(graded),
            "passed": sum(row["grade"]["passed"] for row in graded),
            "errors": len(rows) - len(graded),
            "mean_fact_accuracy": (
                sum(row["grade"]["fact_accuracy"] for row in graded) / len(graded)
                if graded
                else None
            ),
        }
    return totals


def run_representation(store, backend, config, source, data_dir, progress=None):
    data_dir.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(data_dir / "experiment.lock", timeout=0):
            return _run(store, backend, config, source, data_dir, progress)
    except Timeout as error:
        raise RuntimeError("Another local experiment is running; wait for it to finish") from error


def _run(store, backend, config, source, data_dir, progress):
    frozen = load_frozen(source)
    reader = backend.manifest(config.reader_model)
    counter = load_counter(data_dir, config.reader_model, reader)
    run_id = uuid.uuid4().hex[:12]
    result = {
        "id": run_id,
        "status": "running",
        "protocol": "representation-v1",
        "version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        "config": config.model_dump(),
        "hardware": {"system": platform.system(), "machine": platform.machine()},
        "reader": reader,
        "tokenizer": counter.manifest,
        "frozen_writer": frozen["writer"],
        "frozen_source": {"id": frozen["id"], "sha256": FROZEN_SHA256},
        "source_sha256": {
            name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in [
                "representation.py",
                "packets.py",
                "store.py",
                "experiment.py",
                "fixtures.py",
                "grading.py",
                "schemas.py",
                "tokens.py",
                "ollama.py",
            ]
        },
        "cases": [],
        "trials": [],
        "baseline_parity": {},
    }
    destination = data_dir / "runs" / f"{run_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)

    def save():
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
        if progress:
            progress(result)

    # Freeze all packets, verify fidelity and original-baseline parity BEFORE inference.
    scheduled = []
    for row in frozen["cases"]:
        case = load_case(row["case"])
        namespace = f"{run_id}.{case.id}.frozen"
        seed_graph(store, namespace, row)
        result["cases"].append(
            {
                "case": case.id,
                "namespace": namespace,
                "history": row["history"],
                "records": row["memory_writer"]["parsed"]["records"],
            }
        )
        if counter.manifest["tokenizer_sha256"] == frozen["tokenizer"]["tokenizer_sha256"]:
            baseline = packets(store, namespace, case, 128, counter)["structured"]["context"]
            original = next(
                t["context"]
                for t in frozen["trials"]
                if t["case"] == case.id and t["condition"] == "structured"
            )
            if baseline != original:
                raise ValueError("Original 128-token baseline changed; do not pool protocols")
            result["baseline_parity"][case.id] = True
        else:
            result["baseline_parity"][case.id] = None
        prepared = {b: packets(store, namespace, case, b, counter) for b in config.budgets}
        for seed in config.seeds:
            scheduled.append(
                {
                    "case": case.id,
                    "seed": seed,
                    "condition": "full_history",
                    "token_budget": None,
                    "namespace": namespace,
                    "context": json.dumps(
                        row["history"], ensure_ascii=False, separators=(",", ":")
                    ),
                }
            )
            for budget in config.budgets:
                for condition in CONDITIONS:
                    scheduled.append(
                        {
                            "case": case.id,
                            "seed": seed,
                            "condition": condition,
                            "token_budget": budget,
                            "namespace": namespace,
                            **prepared[budget][condition],
                        }
                    )
    result["planned_trials"] = len(scheduled)
    # Mix workflows, seeds, allowances and methods; no method always benefits from first load.
    random.Random(config.seeds[0]).shuffle(scheduled)
    save()
    start = time.perf_counter()
    for trial in scheduled:
        case = load_case(trial["case"])
        trial["context_bytes"] = len(trial["context"].encode())
        trial["historical_tokens"] = counter.history_tokens(trial["context"])
        try:
            if trial["token_budget"] and trial["historical_tokens"] > trial["token_budget"]:
                raise ValueError("Fixed-selection compact packet exceeds allowance; retained")
            prompt = json.dumps(
                {
                    "historical_context": trial["context"],
                    "current_request": case.request,
                    "fact_fields": case.probe_fields,
                    "allowed_actions": {
                        name: ACTION_DESCRIPTIONS[name] for name in case.allowed_actions
                    },
                },
                ensure_ascii=False,
            )
            answer, observation = backend.generate(
                config.reader_model,
                READER_SYSTEM,
                prompt,
                Continuation,
                trial["seed"],
                settings=config.reader_settings,
                counter=counter,
                json_schema=continuation_schema(case),
            )
            trial.update(model=observation, grade=grade(case.id, answer), status="graded")
        except (ModelFailure, ValueError) as error:
            trial.update(
                status=error.kind if isinstance(error, ModelFailure) else "packet_error",
                error=str(error),
            )
            if isinstance(error, ModelFailure):
                trial["model"] = error.observation
        result["trials"].append(trial)
        save()
    result.update(
        status="completed",
        wall_seconds=round(time.perf_counter() - start, 3),
        totals=summarize(result["trials"]),
    )
    save()
    return result
