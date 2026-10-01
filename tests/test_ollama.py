import json

import httpx
import pytest

from compactionlab.ollama import ModelFailure, Ollama
from compactionlab.schemas import Continuation


def test_requests_are_fresh_schema_constrained_and_observable():
    observed = []

    def respond(request):
        observed.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "facts": {"status": "pending"},
                            "next_actions": [],
                            "complete": False,
                            "evidence_ids": [],
                        }
                    )
                },
                "done_reason": "stop",
                "prompt_eval_count": 100,
                "eval_count": 30,
            },
        )

    backend = Ollama(transport=httpx.MockTransport(respond))
    try:
        answer, observation = backend.generate("model", "system", "data", Continuation, 42)
        assert not answer.complete
        assert observation["prompt_tokens"] == 100
        assert len(observed[0]["messages"]) == 2
        assert observed[0]["think"] is False
        assert observed[0]["format"]["additionalProperties"] is False
    finally:
        backend.close()


@pytest.mark.parametrize(
    "response",
    [
        {"done_reason": "length", "message": {"content": "{}"}},
        {"done_reason": "stop", "message": {"content": "not JSON"}},
    ],
)
def test_model_errors_preserve_raw_observation(response):
    backend = Ollama(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response))
    )
    try:
        with pytest.raises(ModelFailure) as error:
            backend.generate("model", "system", "data", Continuation, 42)
        assert error.value.observation["response"] == response
    finally:
        backend.close()
