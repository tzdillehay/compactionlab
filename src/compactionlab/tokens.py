"""Prepared, hash-bound Qwen tokenizers. No network access during evaluation."""

import hashlib
import json
from pathlib import Path

import httpx
from tokenizers import Tokenizer

UPSTREAM = {f"qwen3:{size}b": f"Qwen/Qwen3-{size}B" for size in (4, 8, 14)}
CALIBRATION_TEXTS = [
    "Contact by SMS. Revision B is pending.",
    '{"budget_cents":"90000","sources":["user-2"]}',
    "Café — 東京\nfee = 499; threshold = 7500",
]


def cache_folder(data_dir, model):
    return Path(data_dir) / "tokenizers" / hashlib.sha256(model.encode()).hexdigest()[:16]


class TokenCounter:
    def __init__(self, path: Path, manifest: dict):
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["tokenizer_sha256"]:
            raise ValueError("Tokenizer integrity check failed; prepare it again")
        self.tokenizer = Tokenizer.from_file(str(path))
        self.manifest = manifest

    def count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def history_tokens(self, text: str) -> int:
        # Budget the escaped string value actually inserted into the reader JSON.
        return self.count(json.dumps(text, ensure_ascii=False))

    @staticmethod
    def chat_text(system, prompt, thinking):
        suffix = " /think" if thinking else " /no_think"
        prefix = "" if thinking else "<think>\n\n</think>\n\n"
        return (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{prompt}{suffix}<|im_end|>\n"
            f"<|im_start|>assistant\n{prefix}"
        )

    def chat_tokens(self, system, prompt, thinking):
        return self.count(self.chat_text(system, prompt, thinking))


def load_counter(data_dir, model, runtime_manifest):
    folder = cache_folder(data_dir, model)
    try:
        metadata = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(
            f"Prepare the tokenizer first: compactionlab prepare-tokenizer --model {model}"
        ) from error
    for key in ("digest", "template_sha256", "ollama_version"):
        if metadata["runtime"][key] != runtime_manifest[key]:
            raise ValueError("Model/runtime changed; prepare and calibrate the tokenizer again")
    if not metadata.get("calibration_passed"):
        raise ValueError("Tokenizer calibration failed; token evaluation is disabled")
    return TokenCounter(folder / "tokenizer.json", metadata)


def prepare_tokenizer(backend, model, data_dir):
    if model not in UPSTREAM:
        raise ValueError("Tokenizer preparation currently supports official qwen3:4b, :8b and :14b")
    runtime = backend.manifest(model)
    folder = cache_folder(data_dir, model)
    folder.mkdir(parents=True, exist_ok=True)
    repository = UPSTREAM[model]
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get(f"https://huggingface.co/api/models/{repository}")
        response.raise_for_status()
        revision = response.json()["sha"]
        if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("Upstream returned an invalid immutable revision")
        response = client.get(
            f"https://huggingface.co/{repository}/resolve/{revision}/tokenizer.json"
        )
        response.raise_for_status()
        if len(response.content) > 25_000_000:
            raise ValueError("Tokenizer exceeds the allowed download size")
    path = folder / "tokenizer.json"
    path.write_bytes(response.content)
    metadata = {
        "repository": repository,
        "revision": revision,
        "tokenizer_sha256": hashlib.sha256(response.content).hexdigest(),
        "runtime": runtime,
        "scope": "Qwen single system/user turn; no tools or images",
        "calibration": [],
        "calibration_passed": False,
    }
    counter = TokenCounter(path, metadata)
    for text in CALIBRATION_TEXTS:
        payload = {
            "model": model,
            "prompt": text,
            "raw": True,
            "stream": False,
            "options": {"num_predict": 1, "num_ctx": 2048},
            "keep_alive": "5m",
        }
        result = backend.client.post("/api/generate", json=payload)
        result.raise_for_status()
        observed = result.json().get("prompt_eval_count")
        metadata["calibration"].append(
            {"kind": "raw", "text": text, "expected": counter.count(text), "observed": observed}
        )
    for thinking in (False, True):
        system, prompt = "Return a brief response.", CALIBRATION_TEXTS[-1]
        payload = {
            "model": model,
            "think": thinking,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "options": {"num_predict": 1, "num_ctx": 2048},
            "keep_alive": "5m",
        }
        result = backend.client.post("/api/chat", json=payload)
        result.raise_for_status()
        metadata["calibration"].append(
            {
                "kind": "chat",
                "thinking": thinking,
                "expected": counter.chat_tokens(system, prompt, thinking),
                "observed": result.json().get("prompt_eval_count"),
            }
        )
    metadata["calibration_passed"] = all(
        row["expected"] == row["observed"] for row in metadata["calibration"]
    )
    (folder / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    if not metadata["calibration_passed"]:
        raise ValueError(f"Token calibration failed: {metadata['calibration']}")
    return metadata
