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
from compactionlab.qualification import run_qualification
from compactionlab.representation import run_representation
from compactionlab.schemas import (
    ExperimentRequest,
    InferenceSettings,
    QualificationRequest,
    RepresentationRequest,
)
from compactionlab.store import Store
from compactionlab.tokens import prepare_tokenizer


def inference_arguments(parser, prefix=""):
    parser.add_argument(f"--{prefix}thinking", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(f"--{prefix}context-tokens", type=int, default=8192)
    parser.add_argument(f"--{prefix}output-tokens", type=int, default=2048)
    parser.add_argument(f"--{prefix}temperature", type=float)
    parser.add_argument(f"--{prefix}top-p", type=float)


def settings_from(args, prefix=""):
    return InferenceSettings(
        thinking=getattr(args, f"{prefix}thinking"),
        context_tokens=getattr(args, f"{prefix}context_tokens"),
        max_output_tokens=getattr(args, f"{prefix}output_tokens"),
        temperature=getattr(args, f"{prefix}temperature"),
        top_p=getattr(args, f"{prefix}top_p"),
    )


def main():
    parser = argparse.ArgumentParser(description="Local external context and model handoff tests")
    parser.add_argument(
        "--data-dir", type=Path, default=Path(os.environ.get("COMPACTIONLAB_DATA_DIR", ".local"))
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="Start the local dashboard and HTTP API on port 8765")
    commands.add_parser("mcp", help="Start the shared-memory MCP stdio server")
    prepare = commands.add_parser(
        "prepare-tokenizer", help="Download and calibrate an official tokenizer"
    )
    prepare.add_argument("--model", default="qwen3:8b")
    qualify = commands.add_parser(
        "qualify", help="Calibrate receiver capability on independent parameterized cases"
    )
    qualify.add_argument("--model", default="qwen3:8b")
    qualify.add_argument("--cases-per-workflow", type=int, default=20)
    qualify.add_argument("--seed", type=int, default=20261001)
    qualify.add_argument("--calculator", action=argparse.BooleanOptionalAction, default=True)
    qualify.add_argument(
        "--workflows", nargs="+", default=["release_handoff", "conversation", "budgeting"]
    )
    inference_arguments(qualify)
    replay = commands.add_parser(
        "replay", help="Compare encodings of the frozen public memory graph"
    )
    replay.add_argument("--source", type=Path, required=True)
    replay.add_argument("--reader", default="qwen3:8b")
    replay.add_argument("--budgets", type=int, nargs="+", default=[128, 256, 384, 512])
    replay.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    inference_arguments(replay, "reader-")
    evaluate = commands.add_parser("evaluate", help="Run a real local-model state probe comparison")
    evaluate.add_argument("--writer", default="qwen3:4b")
    evaluate.add_argument("--reader", default="qwen3:8b")
    evaluate.add_argument("--repetitions", type=int, default=1)
    evaluate.add_argument("--byte-budget", type=int, default=6000)
    evaluate.add_argument("--token-budget", type=int)
    inference_arguments(evaluate, "writer-")
    inference_arguments(evaluate, "reader-")
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
    elif args.command == "replay":
        config = RepresentationRequest(
            reader_model=args.reader,
            budgets=args.budgets,
            seeds=args.seeds,
            reader_settings=settings_from(args, "reader_"),
        )
        execute(config, data_dir, qualification=False, source=args.source)
    elif args.command == "evaluate":
        config = ExperimentRequest(
            writer_model=args.writer,
            reader_model=args.reader,
            repetitions=args.repetitions,
            byte_budget=args.byte_budget,
            seed=args.seed,
            cases=args.cases,
            token_budget=args.token_budget,
            writer_settings=settings_from(args, "writer_"),
            reader_settings=settings_from(args, "reader_"),
        )
        execute(config, data_dir, qualification=False)
    elif args.command == "qualify":
        config = QualificationRequest(
            model=args.model,
            cases_per_workflow=args.cases_per_workflow,
            seed=args.seed,
            calculator=args.calculator,
            workflows=args.workflows,
            settings=settings_from(args),
        )
        execute(config, data_dir, qualification=True)
    else:
        backend = Ollama()
        try:
            print(json.dumps(prepare_tokenizer(backend, args.model, data_dir), indent=2))
        finally:
            backend.close()


def execute(config, data_dir, qualification, source=None):
    backend = Ollama()
    last_count = -1

    def progress(result):
        nonlocal last_count
        count = len(result["trials"])
        if count != last_count:
            print(
                json.dumps({"run_id": result["id"], "status": result["status"], "trials": count}),
                flush=True,
            )
            last_count = count

    try:
        if qualification:
            result = run_qualification(backend, config, data_dir, progress)
        elif source is not None:
            result = run_representation(
                Store(data_dir / "memory.sqlite3"), backend, config, source, data_dir, progress
            )
        else:
            result = run_experiment(
                Store(data_dir / "memory.sqlite3"), backend, config, data_dir, progress
            )
        print(
            json.dumps(
                {
                    "id": result["id"],
                    "totals": result["totals"],
                    "qualified": result.get("qualified"),
                },
                indent=2,
            )
        )
    finally:
        backend.close()


if __name__ == "__main__":
    main()
