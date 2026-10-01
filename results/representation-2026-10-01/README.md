# Frozen memory encoding results — October 1, 2026

**153 planned receiving calls, with every outcome retained.** This is a development ablation of three known checkpoints, not held-out evaluation. Qwen3 4B's frozen writer output goes to qwen3:8b with reasoning disabled. No memory content, writer links, reader prompt or grading was repaired between conditions.

Hardware note: Apple M5 Pro, 24 GB unified memory; Ollama 0.35.0, Q4_K_M, Metal. Recorded platform: {'system': 'Darwin', 'machine': 'arm64'}. Model/runtime/tokenizer manifests and exact sampling settings are in the trace. Input is preflighted with output reserve, and complete rendered-input counts are audited.

## Strict recall

Cells are passes / planned, including errors as failures. Each bounded cell repeats one task with 3 seeds. Full references have the same seed count per workflow and are repeated in the table for comparison. They are not new qualification results.

| Workflow        | Historical tokens | Verbose | Compact | Compact fixed selection | Recent | Full reference |
| --------------- | ----------------: | ------: | ------: | ----------------------: | -----: | -------------: |
| release_handoff |               128 |     0/3 |     0/3 |                     0/3 |    3/3 |            3/3 |
| release_handoff |               256 |     0/3 |     0/3 |                     0/3 |    3/3 |            3/3 |
| release_handoff |               384 |     0/3 |     0/3 |                     0/3 |    3/3 |            3/3 |
| release_handoff |               512 |     0/3 |     0/3 |                     0/3 |    3/3 |            3/3 |
| conversation    |               128 |     0/3 |     0/3 |                     0/3 |    3/3 |            3/3 |
| conversation    |               256 |     0/3 |     0/3 |                     0/3 |    3/3 |            3/3 |
| conversation    |               384 |     3/3 |     2/3 |                     3/3 |    3/3 |            3/3 |
| conversation    |               512 |     3/3 |     3/3 |                     3/3 |    3/3 |            3/3 |
| budgeting       |               128 |     0/3 |     0/3 |                     0/3 |    0/3 |            0/3 |
| budgeting       |               256 |     0/3 |     0/3 |                     0/3 |    0/3 |            0/3 |
| budgeting       |               384 |     0/3 |     0/3 |                     0/3 |    0/3 |            0/3 |
| budgeting       |               512 |     0/3 |     0/3 |                     0/3 |    0/3 |            0/3 |

## Fact recall, separate from complete-task passes

Cells are mean correct fact fields across seeds. They exclude action, completion and evidence checks, so factual gains can coexist with complete-task failures. The budget workflow failed every fresh full-history reference and remains diagnostic.

| Workflow        | Historical tokens | Verbose | Compact | Fixed selection | Recent |
| --------------- | ----------------: | ------: | ------: | --------------: | -----: |
| release_handoff |               128 |    0.0% |    0.0% |            0.0% | 100.0% |
| release_handoff |               256 |    0.0% |    0.0% |            0.0% | 100.0% |
| release_handoff |               384 |  100.0% |  100.0% |          100.0% | 100.0% |
| release_handoff |               512 |  100.0% |  100.0% |          100.0% | 100.0% |
| conversation    |               128 |   25.0% |   25.0% |           25.0% | 100.0% |
| conversation    |               256 |    0.0% |    0.0% |            0.0% | 100.0% |
| conversation    |               384 |  100.0% |   91.7% |          100.0% | 100.0% |
| conversation    |               512 |  100.0% |  100.0% |          100.0% | 100.0% |
| budgeting       |               128 |    0.0% |    0.0% |            0.0% |  23.8% |
| budgeting       |               256 |    0.0% |   42.9% |            0.0% |  57.1% |
| budgeting       |               384 |   42.9% |   85.7% |           52.4% |  57.1% |
| budgeting       |               512 |   57.1% |   85.7% |           85.7% |  57.1% |

## Paired changes from verbose encoding

A win is a failure becoming a strict pass on the same case, allowance and seed; a regression is a pass becoming a failure. These repeats are not independent tasks.

| Condition      | Wins | Regressions | Same pass/fail |
| -------------- | ---: | ----------: | -------------: |
| compact        |    0 |           1 |             35 |
| compact_fixed  |    0 |           0 |             36 |
| recent_history |   18 |           0 |             18 |

## Packet coverage and resource observations

The encoding-only control preserves exactly the verbose selection. Adaptive compact selection may admit different records, including stale or irrelevant ones. Selection and token size do not imply accurate recall.

| Workflow        | Allowance | Verbose records / tokens | Compact records / tokens | Fixed compact tokens |
| --------------- | --------: | -----------------------: | -----------------------: | -------------------: |
| release_handoff |       128 |                   1 / 87 |                   1 / 71 |                   71 |
| release_handoff |       256 |                  2 / 186 |                  3 / 211 |                  146 |
| release_handoff |       384 |                  2 / 319 |                  3 / 353 |                  292 |
| release_handoff |       512 |                  3 / 504 |                  3 / 466 |                  466 |
| conversation    |       128 |                   1 / 93 |                   1 / 80 |                   80 |
| conversation    |       256 |                  2 / 228 |                  2 / 194 |                  194 |
| conversation    |       384 |                  3 / 382 |                  3 / 339 |                  333 |
| conversation    |       512 |                  4 / 481 |                  5 / 475 |                  411 |
| budgeting       |       128 |                   1 / 88 |                   1 / 72 |                   72 |
| budgeting       |       256 |                  2 / 187 |                  1 / 241 |                  147 |
| budgeting       |       384 |                  2 / 343 |                  2 / 381 |                  303 |
| budgeting       |       512 |                  3 / 501 |                  3 / 443 |                  443 |

0 retained errors. Rendered-input token audits matched on 153/153 calls with reported input counts. Lossless packet reconstruction passed before inference. Original 128-token baseline parity: {'release_handoff': True, 'conversation': True, 'budgeting': True} (null means a different tokenizer). Packet construction runs once per case/budget/encoding; its saved timing is reused across seeds, not independent latency samples.

| Condition      | Median receiving wall seconds | Median input tokens | Median output tokens |
| -------------- | ----------------------------: | ------------------: | -------------------: |
| full_history   |                         3.036 |                 578 |                   78 |
| structured     |                         2.932 |               555.5 |                 73.5 |
| compact        |                         2.929 |               583.5 |                   61 |
| compact_fixed  |                         2.946 |                 521 |                 67.5 |
| recent_history |                         2.875 |                 470 |                   77 |

Descriptive timings mix warm/cold calls and different packet lengths and output content; they do not establish a speed advantage. Writer extraction cost was paid in the previous frozen source run, not repeated or included in these timings. These short source histories can fit within some allowances while their extracted graphs cannot. Compare recent history before claiming an advantage from external memory.

The original unaided budget problem is diagnostic when its full-history control fails; different calculator-aided qualification tasks do not qualify it. Any improvements or regressions here need replication on new tasks and other model families before broader claims.

## Reproduce

```sh
uv sync --locked
uv run compactionlab prepare-tokenizer --model qwen3:8b
uv run compactionlab replay --source results/token-budget-2026-10-01/1b62ebbc316d.json --budgets 128 256 384 512 --seeds 42 43 44
uv run python scripts/export_representation.py SAVED_RUN_ID --source-commit aaeb24a3b32cd5b28b537a0ec82fde2f8caf1e8e
```

[Frozen source](https://github.com/tzdillehay/compactionlab/tree/aaeb24a3b32cd5b28b537a0ec82fde2f8caf1e8e) · [Raw trace](18fbde355da7.json) · [Integrity manifest](manifest.json) · [Protocol](../../docs/representation.md)
