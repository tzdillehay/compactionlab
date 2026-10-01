"""Local Ollama calls with schema validation and no hidden retry/repair."""

import hashlib
import json
import time

import httpx
from pydantic import BaseModel


class ModelFailure(RuntimeError):
    def __init__(self, message: str, observation: dict | None = None, kind="backend_error"):
        super().__init__(message)
        self.observation = observation or {}
        self.kind = kind


class Ollama:
    def __init__(self, base_url="http://127.0.0.1:11434", transport=None):
        self.client = httpx.Client(base_url=base_url, timeout=240, transport=transport)

    def close(self):
        self.client.close()

    def models(self):
        response = self.client.get("/api/tags")
        response.raise_for_status()
        return response.json()["models"]

    def manifest(self, name):
        models = self.models()
        model = next((item for item in models if item["name"] == name), None)
        if model is None:
            raise ValueError(f"Model {name!r} is not installed; use ollama pull first")
        version = self.client.get("/api/version")
        version.raise_for_status()
        show = self.client.post("/api/show", json={"model": name})
        show.raise_for_status()
        description = show.json()
        return {
            "name": name,
            "digest": model["digest"],
            "details": model.get("details", {}),
            "ollama_version": version.json()["version"],
            "template_sha256": hashlib.sha256(description.get("template", "").encode()).hexdigest(),
            "parameters": description.get("parameters", ""),
        }

    def generate(
        self,
        model: str,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        seed: int,
        json_schema: dict | None = None,
    ):
        payload = {
            "model": model,
            "stream": False,
            "think": False,
            "format": json_schema or schema.model_json_schema(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "seed": seed,
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 20,
                "num_ctx": 8192,
                "num_predict": 2048,
            },
            "keep_alive": "5m",
        }
        start = time.perf_counter()
        try:
            response = self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ModelFailure(
                f"Local model backend failed: {error}", {"request": payload}
            ) from error
        observation = {
            "request": payload,
            "response": result,
            "wall_seconds": round(time.perf_counter() - start, 6),
            "prompt_tokens": result.get("prompt_eval_count"),
            "output_tokens": result.get("eval_count"),
            "load_seconds": result.get("load_duration", 0) / 1e9,
            "inference_seconds": result.get("eval_duration", 0) / 1e9,
        }
        if result.get("done_reason") == "length":
            raise ModelFailure(
                "Model response reached its generation limit", observation, kind="output_error"
            )
        try:
            answer = schema.model_validate_json(result["message"]["content"])
        except (ValueError, KeyError) as error:
            raise ModelFailure(
                f"Model output does not match the schema: {error}", observation, kind="output_error"
            ) from error
        observation["parsed"] = json.loads(answer.model_dump_json())
        return answer, observation
