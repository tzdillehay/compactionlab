# Historical-token accounting smoke — October 1, 2026

3 short synthetic checkpoints, five conditions, 15 planned probes, 128 historical tokens. Writer: qwen3:4b; receiver: qwen3:8b. Inference settings and repetitions are recorded in the trace. This tests budget enforcement through the actual local service and dashboard. It is separate from the receiver qualification and original byte-budget smoke. It uses the original fixtures without a calculator observation; qualification on the aided parameterized tasks does not qualify these different tasks.

The allowance counts the escaped JSON string value inserted as historical_context, including metadata. Full history is an unbounded reference. Recent history keeps complete events; record retrieval keeps complete dependency groups; an over-budget summary becomes a retained writer error. The summary writer still uses the original 1400-character instruction; it is not trained or prompted to optimize this token allowance.

| Method         | Passes / planned | Graded | Errors | Largest bounded history tokens |
| -------------- | ---------------: | -----: | -----: | -----------------------------: |
| full_history   |              2/3 |      3 |      0 |      323 (unbounded reference) |
| recent_history |              2/3 |      3 |      0 |                            119 |
| summary        |              1/3 |      2 |      1 |                            122 |
| plain          |              2/3 |      3 |      0 |                            128 |
| structured     |              0/3 |      3 |      0 |                             93 |

Full rendered-input token audits matched on 14/14 reader calls. Runtime costs and all unavailable conditions are retained in the raw trace. Input/output costs, extraction costs, and retrieval timing are separate from the historical allowance. This does not establish a recall-speed or accuracy improvement.

Median measured record-retrieval time: 3.917 ms over 6 tiny-store calls, including token budget checks. This excludes model inference and network/client overhead and is not a scale benchmark.

## Reproduce

```sh
uv sync --locked
uv run compactionlab prepare-tokenizer --model qwen3:8b
uv run compactionlab evaluate --writer qwen3:4b --reader qwen3:8b --token-budget 128
uv run python scripts/export_token_smoke.py SAVED_RUN_ID
```

[Raw trace](1b62ebbc316d.json) · [Integrity manifest](manifest.json) · [Token protocol](../../docs/qualification.md)
