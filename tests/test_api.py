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
