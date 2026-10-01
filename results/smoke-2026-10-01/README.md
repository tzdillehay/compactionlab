# Local smoke results — October 1, 2026

**Engineering smoke, not evidence of general memory-method superiority.**

90 state probes: six configurations × three synthetic task templates × five methods. One repetition per configuration. All failures and unavailable conditions are retained. The same-model runs are controls. Compare methods within a fixed receiver and allowance.

Hardware: Apple M5 Pro, 24 GB unified memory; Ollama 0.35.0, Qwen3 4B/8B Q4_K_M with thinking disabled. Runtime reported model weights fully in GPU memory. Model digests and every request/response are in the run JSON.

## Strict passes and coverage

Cells are passed/graded; `+Ne` means N unavailable/error trials. Each cell has 3 planned probes.

| Writer → receiver | Historical bytes | Full | Recent | Summary | Plain | State + evidence |
| --- | ---: | --- | --- | --- | --- | --- |
| qwen3:4b → qwen3:8b | 6000 | 2/3 | 2/3 | 1/3 | 2/3 | 2/3 |
| qwen3:8b → qwen3:4b | 6000 | 0/3 | 0/3 | 1/3 | 1/2 +1e | 0/2 +1e |
| qwen3:4b → qwen3:4b | 6000 | 0/3 | 0/3 | 1/3 | 1/3 | 0/3 |
| qwen3:8b → qwen3:8b | 6000 | 2/3 | 2/3 | 1/3 | 2/2 +1e | 2/2 +1e |
| qwen3:4b → qwen3:8b | 2000 | 2/3 | 2/3 | 1/3 | 2/3 | 1/3 |
| qwen3:8b → qwen3:4b | 2000 | 0/3 | 0/3 | 1/3 | 1/2 +1e | 0/2 +1e |

## Per-task outcomes

Passes / graded, pooled here only as a coverage diagnostic across configurations; this is not a comparison that controls receiver capability.

| Task | Full | Recent | Summary | Plain | State + evidence |
| --- | --- | --- | --- | --- | --- |
| release_handoff | 3/6 | 3/6 | 2/6 | 3/6 | 2/6 |
| conversation | 3/6 | 3/6 | 4/6 | 6/6 | 3/6 |
| budgeting | 0/6 | 0/6 | 0/6 | 0/3 | 0/3 |

## Reader resource observations

These mix warm/cold calls and different receivers; descriptive only. Writer cost is recorded separately in each case's summary_writer/memory_writer fields.

| Method | Median wall seconds | Median reported load seconds | Median input tokens |
| --- | ---: | ---: | ---: |
| full_history | 1.484 | 0.001 | 575 |
| recent_history | 1.735 | 0.001 | 575 |
| summary | 1.575 | 0.001 | 364 |
| plain | 1.956 | 0.001 | 577 |
| structured | 2.565 | 0.003 | 827 |

## What this establishes

The service, real local inference, external memory transfer and independent grading run end to end. Structured records have not established an advantage in this pilot. Short histories produce ceiling effects, and the smaller receiver fails some full-history controls. Budgeting arithmetic/action failures also occur without compaction, so they cannot be attributed to memory alone. Model-written links and facts can be wrong; original source records make those errors inspectable.

Next: qualify a capable receiver on independent tasks, add deterministic calculation tools equally to every condition, compare source-span preservation with free-text extraction, and add true tool continuations with token-matched context allowances.

## Failed checks

| Check | Count among graded probes |
| --- | ---: |
| fact:budget_cents | 1 |
| fact:cedar_payment_cents | 17 |
| fact:extra_cents | 23 |
| fact:fee_cents | 3 |
| fact:minimums_cents | 23 |
| fact:oak_payment_cents | 17 |
| fact:pending | 2 |
| fact:pine_payment_cents | 24 |
| fact:target | 1 |
| fact:threshold_cents | 1 |
| honest_completion | 4 |
| no_prohibited_actions | 6 |
| no_unsupported_evidence | 25 |
| required_actions | 23 |

## Unavailable conditions

- `Unknown or self-referential link in record task-state-001`

## Reproduce and inspect

```sh
uv sync --locked
uv run python scripts/run_smoke.py
uv run python scripts/export_smoke.py
```

Exact generations and timing may differ. Digests, seeds, settings, histories, memory proposals, rendered context, source-code hashes and raw responses are retained.

## Runs

- [c75a14b5b339](c75a14b5b339.json)
- [b49511fbb2d9](b49511fbb2d9.json)
- [15c76217ac4f](15c76217ac4f.json)
- [9230375b53b6](9230375b53b6.json)
- [e46329f7de38](e46329f7de38.json)
- [6d90b58b4498](6d90b58b4498.json)

Earlier v1/v2 contract-development runs are in [development](development/). They are not pooled with the frozen v3 matrix. [Manifest and hashes](manifest.json).
