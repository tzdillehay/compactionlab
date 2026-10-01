import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compactionlab.api import create_app


def save(folder, identifier, *, protocol="state-probe-v4", trials=None, token_budget=None):
    folder.mkdir(parents=True, exist_ok=True)
    result = {
        "id": identifier,
        "created_at": "2026-10-01T12:00:00+00:00",
        "protocol": protocol,
        "status": "completed",
        "config": {
            "writer_model": "qwen3:4b",
            "reader_model": "qwen3:8b",
            "token_budget": token_budget,
            "byte_budget": 6000,
        },
        "trials": trials or [],
    }
    (folder / f"{identifier}.json").write_text(json.dumps(result), encoding="utf-8")
    return result


def test_empty_overview_needs_no_model_service(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        result = client.get("/api/overview").json()
        assert result["summary"]["saved_probes"] == 0
        assert result["summary"]["latest_at"] is None
        assert result["studies"] == result["development"] == []


def test_inventory_deduplicates_traces_keeps_errors_and_separates_old_contracts(tmp_path):
    data = tmp_path / "local"
    published = tmp_path / "public"
    save(published, "a" * 12)
    trials = [
        {
            "case": "conversation",
            "status": "graded",
            "grade": {"passed": True, "fact_accuracy": 1},
            "model": {"wall_seconds": 1},
        },
        {
            "case": "conversation",
            "status": "graded",
            "grade": {"passed": False, "fact_accuracy": 0.5},
            "model": {"wall_seconds": 3},
        },
        {"case": "conversation", "status": "writer_error"},
    ]
    local = save(data / "runs", "a" * 12, trials=trials, token_budget=128)
    save(published / "development", "b" * 12, protocol="state-probe-v2", trials=trials[:1])
    with TestClient(create_app(data, published_dir=published)) as client:
        result = client.get("/api/overview").json()
        assert result["summary"]["runs"] == 2
        assert result["summary"]["saved_probes"] == 4
        assert result["summary"]["development_runs"] == 1
        assert result["studies"][0]["id"] == "tokens"
        metrics = result["studies"][0]["metrics"]
        assert metrics == {
            "saved": 3,
            "graded": 2,
            "passed": 1,
            "errors": 1,
            "mean_fact_accuracy": 0.75,
            "median_receiver_seconds": 2,
            "timed_responses": 2,
        }
        assert result["studies"][0]["runs"][0]["published"] is False
        assert client.get(f"/api/runs/{'a' * 12}").json() == local
        assert client.get(f"/api/qualifications/{'a' * 12}").status_code == 404
        assert len(client.get("/api/runs").json()) == 2


def test_inventory_is_not_limited_to_thirty_runs_and_updates_after_new_result(tmp_path):
    for index in range(35):
        save(tmp_path / "runs", f"{index:012x}")
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/overview").json()["summary"]["runs"] == 35
        assert len(client.get("/api/runs").json()) == 35
        save(tmp_path / "runs", "f" * 12)
        assert client.get("/api/overview").json()["summary"]["runs"] == 36


def test_public_checkout_overview_uses_frozen_evidence_without_inference(tmp_path):
    published = Path(__file__).resolve().parents[1] / "results"
    with TestClient(create_app(tmp_path, published_dir=published)) as client:
        result = client.get("/api/overview").json()
        assert result["summary"]["saved_probes"] == 687
        assert result["summary"]["runs"] == 15
        assert result["summary"]["studies"] == 4
        assert result["summary"]["development_runs"] == 5
        encoding = next(s for s in result["studies"] if s["id"] == "encoding")
        assert encoding["metrics"]["saved"] == 153
        assert encoding["metrics"]["passed"] == 47
        paired = encoding["runs"][0]["encoding"]
        assert (paired["pairs"], paired["wins"], paired["losses"], paired["ties"]) == (36, 0, 1, 35)
        assert paired["same_selection_token_reduction"] == pytest.approx(
            [0.0753968254, 0.2150537634]
        )
        qualification = next(s for s in result["studies"] if s["id"] == "qualification")
        assert qualification["metrics"]["saved"] == 240
        assert qualification["metrics"]["passed"] == 150
        assert client.get("/api/runs/18fbde355da7").json()["protocol"] == "representation-v1"
        assert (
            client.get("/api/qualifications/07deef2b5d38").json()["protocol"] == "qualification-v3"
        )
