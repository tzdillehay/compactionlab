import json

import httpx
import pytest

from compactionlab.ollama import ModelFailure, Ollama
from compactionlab.schemas import Continuation, InferenceSettings


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


def test_thinking_settings_and_context_capacity_are_observable(prepared_counter):
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": '{"facts":{},"next_actions":[],"complete":false,"evidence_ids":[]}',
                    "thinking": "Synthetic offline reasoning.",
                },
                "done_reason": "stop",
                "prompt_eval_count": prepared_counter.chat_tokens("system", "data", True),
                "eval_count": 40,
            },
        )

    backend = Ollama(transport=httpx.MockTransport(respond))
    try:
        _, observation = backend.generate(
            "model",
            "system",
            "data",
            Continuation,
            42,
            settings=InferenceSettings(thinking=True, max_output_tokens=4096),
            counter=prepared_counter,
        )
        assert requests[0]["think"] is True
        assert requests[0]["options"]["temperature"] == 0.6
        assert requests[0]["options"]["top_p"] == 0.95
        assert observation["prompt_accounting_match"]
        assert observation["thinking_text"] == "Synthetic offline reasoning."
        with pytest.raises(ModelFailure) as error:
            backend.generate(
                "model",
                "system",
                "data" * 1000,
                Continuation,
                42,
                settings=InferenceSettings(context_tokens=1024, max_output_tokens=1000),
                counter=prepared_counter,
            )
        assert error.value.kind == "capacity_error" and len(requests) == 1
    finally:
        backend.close()


def test_accounting_mismatch_is_retained_not_silently_accepted(prepared_counter):
    backend = Ollama(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"message": {"content": "{}"}, "prompt_eval_count": 1}
            )
        )
    )
    try:
        with pytest.raises(ModelFailure) as error:
            backend.generate("model", "system", "data", Continuation, 42, counter=prepared_counter)
        assert error.value.kind == "accounting_error"
        assert error.value.observation["response"]["prompt_eval_count"] == 1
    finally:
        backend.close()
