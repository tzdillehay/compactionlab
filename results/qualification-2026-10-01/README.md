# Receiver qualification — October 1, 2026

240 probes: 60 parameterized cases × two source conditions × two inference configurations. The same Qwen3 8B Q4_K_M digest and fixture instances are used in both configurations. Every planned outcome, failure and raw response is retained. This is a development capability screen, not evidence of memory-method superiority or autonomous competence.

Recorded platform: Darwin / arm64; Ollama 0.35.0. Reference measurement: Apple M5 Pro, 24 GB unified memory, Metal backend. Windows inference was not measured.

## Full-history qualification

At least 20 full-history cases and 90% strict success per workflow are required. Errors count as failures. Minimal sources are an annotated diagnostic subset, not a learned memory policy.

| Thinking | Workflow        | Full passes / planned | Minimal passes / planned | Full errors | Gate          |
| -------- | --------------- | --------------------: | -----------------------: | ----------: | ------------- |
| False    | release_handoff |                 20/20 |                    15/20 |           0 | qualified     |
| False    | conversation    |                 15/20 |                    15/20 |           0 | not qualified |
| False    | budgeting       |                 20/20 |                    16/20 |           0 | qualified     |
| True     | release_handoff |                 10/20 |                    11/20 |           0 | not qualified |
| True     | conversation    |                  4/20 |                     3/20 |           0 | not qualified |
| True     | budgeting       |                 11/20 |                    10/20 |           0 | not qualified |

## What failed

Strict success includes the completion-only evidence contract. Citing a correct source for an unfinished task still fails that contract, which requires an empty evidence list. The components below separate this instruction-following failure from wrong facts or completion state. Counts use all planned full-history trials; errors fail every component. These diagnostics do not replace the frozen operational gate.

| Thinking | Workflow        | All facts correct | Action checks met | Completion correct | Evidence contract met |
| -------- | --------------- | ----------------: | ----------------: | -----------------: | --------------------: |
| False    | release_handoff |             20/20 |             20/20 |              20/20 |                 20/20 |
| False    | conversation    |             15/20 |             19/20 |              19/20 |                 19/20 |
| False    | budgeting       |             20/20 |             20/20 |              20/20 |                 20/20 |
| True     | release_handoff |             20/20 |             19/20 |              19/20 |                 11/20 |
| True     | conversation    |             18/20 |             20/20 |              20/20 |                  5/20 |
| True     | budgeting       |             20/20 |             20/20 |              20/20 |                 11/20 |

## Resource observations

Both modes use 8192 context tokens. Non-thinking uses a 2048-token output allowance, temperature 0.7 and top-p 0.8; thinking uses 6144, 0.6 and 0.95. This compares inference configurations, not thinking alone. Cold/warm loading is retained per call, so these mixed-call medians are descriptive. The non-thinking run precedes the thinking run; configuration order is not randomized.

| Thinking | Median wall seconds | Median input tokens | Median output tokens | Token audits matching |
| -------- | ------------------: | ------------------: | -------------------: | --------------------: |
| False    |               1.958 |                 477 |                   69 |               120/120 |
| True     |              16.146 |                 471 |                  603 |               120/120 |

## Failed checks

| Thinking | Check                 | Count |
| -------- | --------------------- | ----: |
| False    | completion_state      |     5 |
| False    | current_evidence      |     7 |
| False    | fact:pending          |    10 |
| False    | fact:validation       |     1 |
| False    | no_prohibited_actions |     1 |
| False    | required_actions      |     4 |
| True     | completion_state      |     2 |
| True     | current_evidence      |    67 |
| True     | fact:pending          |     6 |
| True     | fact:validation       |     2 |
| True     | no_prohibited_actions |     1 |
| True     | required_actions      |     1 |

## Interpretation and boundaries

The receiver reports current facts, actions, completion and evidence. Shipping observations come from actual fixture assertions; deliveries and payment receipts are simulated. A deterministic calculator receives visible fixture inputs and supplies a draft to both conditions. This does not test model-driven tool selection or real-world actions.

Qualification applies only to these shared-template state probes. Twenty parameterized cases are an operational screen, not broad generalization evidence. No memory-method comparison is made here. A passing full-history gate does not imply that minimal sources, long histories, or actual agent continuations will succeed.

The calibrated historical unit includes JSON escaping. Full prompt rendering is audited against Ollama on every call. Tokenizer revision, SHA-256, model digest and template hash are included in each trace. Raw reasoning and output-length failures are retained.

V1/V2 development traces and their original grades are retained separately in [development](development/). Their evidence-contract corrections are described in the [protocol](../../docs/qualification.md). They are not pooled with V3 or the original smoke report.

## Reproduce

```sh
uv sync --locked
uv run compactionlab prepare-tokenizer --model qwen3:8b
uv run python scripts/run_qualification_study.py
uv run python scripts/export_qualification.py
```

Generations and timings may vary. [Manifest and integrity hashes](manifest.json).

## Runs

- [07deef2b5d38](07deef2b5d38.json)
- [45fa23337531](45fa23337531.json)
