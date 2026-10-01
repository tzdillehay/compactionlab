"""Loopback-only HTTP service and dashboard; one model experiment at a time."""

import json
import re
import threading
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from compactionlab import __version__
from compactionlab.experiment import run_experiment
from compactionlab.ollama import Ollama
from compactionlab.qualification import run_qualification
from compactionlab.schemas import (
    ContextRequest,
    ExperimentRequest,
    QualificationRequest,
    WriteBatch,
)
from compactionlab.store import RevisionConflict, Store
from compactionlab.tokens import load_counter


def create_app(data_dir: Path, ollama_url="http://127.0.0.1:11434"):
    store = Store(data_dir / "memory.sqlite3")
    app = FastAPI(title="CompactionLab", version=__version__, docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    busy = threading.Lock()
    jobs = {}
    assets = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=assets), name="static")

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in {"http://127.0.0.1:8765", "http://localhost:8765"}:
            return JSONResponse({"detail": "Cross-origin access is disabled"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(RevisionConflict)
    async def revision_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(KeyError)
    async def missing_error(request, error):
        return JSONResponse({"detail": "Namespace or result not found"}, status_code=404)

    @app.get("/")
    def index():
        return FileResponse(assets / "index.html")

    @app.get("/docs")
    def docs():
        return FileResponse(assets / "api.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "compactionlab", "version": __version__}

    @app.get("/api/models")
    def models():
        backend = Ollama(ollama_url)
        try:
            return {"models": backend.models()}
        except Exception as error:
            raise HTTPException(503, "Local model server is unavailable") from error
        finally:
            backend.close()

    @app.get("/api/namespaces")
    def namespaces():
        return store.namespaces()

    @app.get("/api/namespaces/{namespace}")
    def snapshot(namespace: str):
        return store.snapshot(namespace)

    @app.post("/api/namespaces/{namespace}/records")
    def write(namespace: str, batch: WriteBatch):
        return {"revision": store.write(namespace, batch)}

    @app.post("/api/namespaces/{namespace}/context")
    def context(namespace: str, query: ContextRequest):
        return store.context(namespace, query)

    def work(job_id, config, qualification=False):
        backend = Ollama(ollama_url)
        try:

            def update(result):
                jobs[job_id] = {
                    "status": result["status"],
                    "run_id": result["id"],
                    "trials": len(result["trials"]),
                    "cases": len(result["cases"]),
                }

            result = (
                run_qualification(backend, config, data_dir, progress=update)
                if qualification
                else run_experiment(store, backend, config, data_dir, progress=update)
            )
            update(result)
        except Exception as error:
            jobs[job_id] = {"status": "failed", "error": str(error)}
        finally:
            backend.close()
            busy.release()

    @app.post("/api/jobs", status_code=202)
    def start(config: ExperimentRequest, tasks: BackgroundTasks):
        backend = Ollama(ollama_url)
        try:
            names = {model["name"] for model in backend.models()}
            if not {config.writer_model, config.reader_model} <= names:
                raise ValueError(
                    "Choose installed local models; the service never downloads weights"
                )
            if config.token_budget is not None:
                load_counter(data_dir, config.reader_model, backend.manifest(config.reader_model))
        finally:
            backend.close()
        if not busy.acquire(blocking=False):
            raise HTTPException(409, "An experiment is already running")
        job_id = uuid.uuid4().hex[:12]
        jobs[job_id] = {"status": "queued", "trials": 0}
        tasks.add_task(work, job_id, config)
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        if job_id not in jobs:
            raise HTTPException(404, "Job not found; completed results persist under /api/runs")
        return jobs[job_id]

    @app.post("/api/qualification/jobs", status_code=202)
    def start_qualification(config: QualificationRequest, tasks: BackgroundTasks):
        backend = Ollama(ollama_url)
        try:
            if config.model not in {model["name"] for model in backend.models()}:
                raise ValueError("Choose an installed local model")
            load_counter(data_dir, config.model, backend.manifest(config.model))
        finally:
            backend.close()
        if not busy.acquire(blocking=False):
            raise HTTPException(409, "An experiment is already running")
        job_id = uuid.uuid4().hex[:12]
        jobs[job_id] = {"status": "queued", "trials": 0}
        tasks.add_task(work, job_id, config, True)
        return {"job_id": job_id}

    @app.get("/api/qualifications")
    def qualifications():
        paths = sorted(
            (data_dir / "qualifications").glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:30]
        return [
            {
                key: value.get(key)
                for key in ["id", "created_at", "status", "config", "totals", "qualified"]
            }
            for path in paths
            if (value := json.loads(path.read_text(encoding="utf-8")))
        ]

    @app.get("/api/qualifications/{run_id}")
    def qualification_result(run_id: str):
        if not re.fullmatch(r"[a-f0-9]{12}", run_id):
            raise HTTPException(400, "Invalid qualification ID")
        path = data_dir / "qualifications" / f"{run_id}.json"
        if not path.is_file():
            raise HTTPException(404, "Qualification not found")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/runs")
    def runs():
        paths = sorted(
            (data_dir / "runs").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:30]
        summaries = []
        for path in paths:
            value = json.loads(path.read_text(encoding="utf-8"))
            summaries.append(
                {key: value.get(key) for key in ["id", "created_at", "status", "config", "totals"]}
            )
        return summaries

    @app.get("/api/runs/{run_id}")
    def run(run_id: str):
        if not re.fullmatch(r"[a-f0-9]{12}", run_id):
            raise HTTPException(400, "Invalid run ID")
        path = data_dir / "runs" / f"{run_id}.json"
        if not path.is_file():
            raise HTTPException(404, "Run not found")
        return json.loads(path.read_text(encoding="utf-8"))

    return app
