"""Frozen six-run engineering smoke matrix. Outputs are real local model responses."""

import json
from pathlib import Path

from compactionlab.experiment import run_experiment
from compactionlab.ollama import Ollama
from compactionlab.schemas import ExperimentRequest
from compactionlab.store import Store

ROOT = Path(__file__).resolve().parents[1]
PLAN = [
    ("qwen3:4b", "qwen3:8b", 6000),
    ("qwen3:8b", "qwen3:4b", 6000),
    ("qwen3:4b", "qwen3:4b", 6000),
    ("qwen3:8b", "qwen3:8b", 6000),
    ("qwen3:4b", "qwen3:8b", 2000),
    ("qwen3:8b", "qwen3:4b", 2000),
]


def main():
    data = ROOT / ".local"
    store = Store(data / "memory.sqlite3")
    backend = Ollama()
    identifiers = []
    try:
        for writer, reader, budget in PLAN:
            print(f"Starting {writer} -> {reader}, {budget} bytes", flush=True)
            config = ExperimentRequest(writer_model=writer, reader_model=reader, byte_budget=budget)
            result = run_experiment(store, backend, config, data)
            identifiers.append(result["id"])
            print(json.dumps({"id": result["id"], "totals": result["totals"]}), flush=True)
        (data / "smoke-run-ids.json").write_text(json.dumps(identifiers, indent=2) + "\n")
    finally:
        backend.close()


if __name__ == "__main__":
    main()
