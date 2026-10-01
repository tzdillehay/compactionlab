from fastapi.testclient import TestClient

from compactionlab.api import create_app


def test_http_memory_lifecycle_and_conflicts(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        body = {
            "expected_revision": 0,
            "events": [{"id": "e", "source": "user", "text": "SMS"}],
            "records": [{"id": "r", "kind": "fact", "text": "Contact by SMS", "source_ids": ["e"]}],
        }
        assert client.post("/api/namespaces/demo/records", json=body).json() == {"revision": 1}
        assert client.post("/api/namespaces/demo/records", json=body).status_code == 409
        context = client.post("/api/namespaces/demo/context", json={"query": "contact"}).json()
        assert context["record_ids"] == ["r"]
        assert client.get("/api/namespaces/missing").status_code == 404
        assert (
            client.post(
                "/api/namespaces/demo/context", json={"query": "x", "byte_budget": 1}
            ).status_code
            == 422
        )


def test_loopback_host_and_origin_boundaries(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
        assert (
            client.get("/api/health", headers={"Origin": "https://evil.example"}).status_code == 403
        )
        assert client.get("/", headers={"Origin": "http://127.0.0.1:8765"}).status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/api/runs/not-an-id").status_code == 400


def test_invalid_sources_do_not_leave_partial_events(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.post(
            "/api/namespaces/demo/records",
            json={
                "expected_revision": 0,
                "events": [{"id": "e", "source": "user", "text": "Hello"}],
                "records": [{"id": "r", "kind": "fact", "text": "bad", "source_ids": ["missing"]}],
            },
        )
        assert response.status_code == 400
        assert client.get("/api/namespaces").json() == []


def test_qualification_jobs_persist_results_and_require_prepared_tokens(tmp_path, monkeypatch):
    import json

    import compactionlab.api as api

    class Backend:
        def __init__(self, *args):
            pass

        def models(self):
            return [{"name": "qwen3:8b"}]

        def manifest(self, name):
            return {"name": name, "digest": "offline"}

        def close(self):
            pass

    monkeypatch.setattr(api, "Ollama", Backend)
    with TestClient(create_app(tmp_path)) as client:
        missing = client.post("/api/qualification/jobs", json={"cases_per_workflow": 4})
        assert missing.status_code == 400 and "Prepare the tokenizer" in missing.json()["detail"]
        monkeypatch.setattr(api, "load_counter", lambda *args: object())

        def run(backend, config, data_dir, progress):
            result = {
                "id": "a" * 12,
                "status": "completed",
                "cases": [],
                "trials": [{"context": "Café 東京"}],
                "config": config.model_dump(),
                "totals": {},
                "qualified": False,
            }
            folder = data_dir / "qualifications"
            folder.mkdir()
            (folder / f"{result['id']}.json").write_text(json.dumps(result), encoding="utf-8")
            progress(result)
            return result

        monkeypatch.setattr(api, "run_qualification", run)
        response = client.post("/api/qualification/jobs", json={"cases_per_workflow": 4})
        assert response.status_code == 202
        job = client.get(f"/api/jobs/{response.json()['job_id']}").json()
        assert job["status"] == "completed" and job["trials"] == 1
        assert client.get("/api/qualifications").json()[0]["id"] == "a" * 12
        assert (
            client.get(f"/api/qualifications/{'a' * 12}").json()["trials"][0]["context"]
            == "Café 東京"
        )
        assert client.get("/api/qualifications/invalid").status_code == 400
