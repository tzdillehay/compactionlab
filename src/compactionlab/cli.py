"""Public CLI. Nothing downloads a model or calls a paid provider automatically."""

import argparse
import json
import os
from pathlib import Path

import uvicorn

from compactionlab.api import create_app
from compactionlab.experiment import run_experiment
from compactionlab.mcp_server import create_server
from compactionlab.ollama import Ollama
from compactionlab.schemas import ExperimentRequest
from compactionlab.store import Store


def main():
    parser = argparse.ArgumentParser(description="Local external context and model handoff tests")
    parser.add_argument(
        "--data-dir", type=Path, default=Path(os.environ.get("COMPACTIONLAB_DATA_DIR", ".local"))
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="Start the local dashboard and HTTP API on port 8765")
    commands.add_parser("mcp", help="Start the shared-memory MCP stdio server")
    evaluate = commands.add_parser("evaluate", help="Run a real local-model state probe comparison")
    evaluate.add_argument("--writer", default="qwen3:4b")
    evaluate.add_argument("--reader", default="qwen3:8b")
    evaluate.add_argument("--repetitions", type=int, default=1)
    evaluate.add_argument("--byte-budget", type=int, default=6000)
    evaluate.add_argument("--seed", type=int, default=42)
    evaluate.add_argument(
        "--cases", nargs="+", default=["release_handoff", "conversation", "budgeting"]
    )
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    if args.command == "serve":
        uvicorn.run(create_app(data_dir), host="127.0.0.1", port=8765, access_log=False)
    elif args.command == "mcp":
        create_server(data_dir).run(transport="stdio")
    else:
        config = ExperimentRequest(
            writer_model=args.writer,
            reader_model=args.reader,
            repetitions=args.repetitions,
            byte_budget=args.byte_budget,
            seed=args.seed,
            cases=args.cases,
        )
        backend = Ollama()
        last_count = -1

        def progress(result):
            nonlocal last_count
            count = len(result["trials"])
            if count != last_count:
                print(
                    json.dumps(
                        {"run_id": result["id"], "status": result["status"], "trials": count}
                    ),
                    flush=True,
                )
                last_count = count

        try:
            result = run_experiment(
                Store(data_dir / "memory.sqlite3"), backend, config, data_dir, progress
            )
            print(json.dumps({"id": result["id"], "totals": result["totals"]}, indent=2))
        finally:
            backend.close()


if __name__ == "__main__":
    main()
