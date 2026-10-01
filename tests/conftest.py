import hashlib
import json

import pytest
from tokenizers import Tokenizer, models, pre_tokenizers, trainers

from compactionlab.tokens import TokenCounter, cache_folder


@pytest.fixture
def prepared_counter(tmp_path):
    tokenizer = Tokenizer(models.BPE())
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.train_from_iterator(
        ['{"sources":["user-2"],"text":"Café 東京"}', "Contact by SMS. Revision B."] * 3,
        trainers.BpeTrainer(vocab_size=320, initial_alphabet=pre_tokenizers.ByteLevel.alphabet()),
    )
    runtime = {
        "name": "qwen3:8b",
        "digest": "offline-only",
        "template_sha256": "offline",
        "ollama_version": "offline",
    }
    folder = cache_folder(tmp_path, "qwen3:8b")
    folder.mkdir(parents=True)
    path = folder / "tokenizer.json"
    tokenizer.save(str(path))
    metadata = {
        "runtime": runtime,
        "tokenizer_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "calibration_passed": True,
        "scope": "offline-test-only",
    }
    (folder / "manifest.json").write_text(json.dumps(metadata), encoding="utf-8")
    return TokenCounter(path, metadata)
