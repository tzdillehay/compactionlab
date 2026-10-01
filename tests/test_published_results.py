import hashlib
import json
from pathlib import Path

from compactionlab.experiment import aggregate
from compactionlab.grading import grade
from compactionlab.schemas import Continuation

ROOT = Path(__file__).resolve().parents[1]


def test_published_trace_integrity_and_independent_grades():
    folder = ROOT / "results/smoke-2026-10-01"
    manifest = json.loads((folder / "manifest.json").read_text())
    count = 0
    for name, expected_hash in manifest["sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected_hash
    for identifier in manifest["run_ids"]:
        result = json.loads((folder / f"{identifier}.json").read_text())
        assert result["protocol"] == "state-probe-v3"
        assert result["totals"] == aggregate(result["trials"])
        for trial in result["trials"]:
            count += 1
            if trial["status"] == "graded":
                answer = Continuation.model_validate(trial["model"]["parsed"])
                assert trial["grade"] == grade(trial["case"], answer)
                assert len(trial["context"].encode()) == trial["context_bytes"]
                if trial["condition"] != "full_history":
                    assert trial["context_bytes"] <= result["config"]["byte_budget"]
    assert count == 90
