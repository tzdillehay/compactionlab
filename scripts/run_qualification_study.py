"""Frozen paired configuration screen; sequential calls to the same local model."""

import json
from pathlib import Path

from compactionlab.ollama import Ollama
from compactionlab.qualification import run_qualification
from compactionlab.schemas import InferenceSettings, QualificationRequest

ROOT = Path(__file__).resolve().parents[1]


def main():
    backend = Ollama()
    ids = []
    try:
        for thinking in (False, True):
            config = QualificationRequest(
                settings=InferenceSettings(
                    thinking=thinking, max_output_tokens=6144 if thinking else 2048
                )
            )

            def progress(result, reasoning=thinking):
                count = len(result["trials"])
                if count % 10 == 0:
                    print(
                        json.dumps(
                            {
                                "id": result["id"],
                                "thinking": reasoning,
                                "trials": count,
                                "status": result["status"],
                            }
                        ),
                        flush=True,
                    )

            result = run_qualification(backend, config, ROOT / ".local", progress)
            ids.append(result["id"])
            (ROOT / ".local/qualification-study-ids.json").write_text(
                json.dumps(ids, indent=2) + "\n", encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        "id": result["id"],
                        "totals": result["totals"],
                        "qualified": result["qualified"],
                    }
                ),
                flush=True,
            )
    finally:
        backend.close()


if __name__ == "__main__":
    main()
