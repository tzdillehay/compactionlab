# Frozen memory encoding experiment

Protocol `representation-v1` compares how the **same model-written memory** survives a handoff.
The writer is Qwen3 4B from published run `1b62ebbc316d`; the receiving model is Qwen3 8B.
This is a development ablation of three known synthetic checkpoints, not held-out evaluation.
There are no new writer calls, record repairs, edited facts, extra calculator observations,
changed grading, or autonomous task execution.

## Question and controls

Does removing empty metadata and sharing original source events make structured memory useful
under a smaller historical allowance? Can the additional records it admits also hurt recall?

| Condition        | Selection                                                         | Representation                                           |
| ---------------- | ----------------------------------------------------------------- | -------------------------------------------------------- |
| `structured`     | Existing lexical ranking, active roots, atomic dependency closure | Original verbose records with per-record sources         |
| `compact`        | Identical ranking and closure; reselect under the same allowance  | Sparse records with a shared chronological source table  |
| `compact_fixed`  | Exactly the IDs selected by `structured`                          | Compact representation; isolates encoding from selection |
| `recent_history` | Complete contiguous suffix of source events                       | Unchanged source-event JSON                              |
| `full_history`   | All source events, once per case and seed                         | Unbounded reference                                      |

The compact format retains record IDs, kinds, text, source references, state, effective state,
nonempty scope/entity fields, links, original source roles/text, and source chronology.
It omits empty strings/lists and includes each source event once. An empty selection is `[]`.
`expand_packet` restores omitted empty fields and verifies exact equality with verbose records
before inference. This proves representation fidelity; it does not prove a receiving model
interprets both formats identically or that the original writer was correct.

The receiving system prompt, fact/action schema, grader, and inference settings are identical
across conditions. Historical allowances count the escaped JSON string actually inserted into
the prompt, including packet metadata. Full rendered chat input is audited against Ollama.
An over-budget fixed-selection packet becomes a retained error, without repair or clipping.

## Frozen first sweep

Three cases × three seeds × four budgets × four bounded conditions, plus nine full-history
controls: **153 planned receiving calls**. Seeds: 42, 43, 44. Budgets: 128, 256, 384, 512.
Qwen3 8B, reasoning disabled, context 8192, output reserve 2048, temperature 0.7, top-p 0.8,
top-k 20, min-p 0. Trial order is shuffled across cases, budgets, conditions, and seeds with
seed 42 before inference. Every call uses a fresh system/user request; no reader state is reused.

Budgets were chosen using an offline token/selection preview of the known development traces.
The 384-token point was added because compact selection retains the corrected budget while
verbose selection excludes it. No new receiving-model outcomes were consulted to select it.
The 128-token verbose contexts must exactly match the previously published baseline when using
the same tokenizer. Source-trace integrity is checked against a fixed SHA-256; modified or private
histories cannot enter this replay protocol.

Passes require all current facts, correct necessary actions, honest completion and appropriate
completion evidence. Report per workflow and allowance, plus seed-paired improvements/regressions;
never pool seed repetitions as independent tasks or present their counts as statistical significance.
The unaided original budget task previously failed its full-history control. Its memory results
remain diagnostic unless these fresh controls demonstrate the receiving model can solve it.
Qualification on different calculator-aided budget tasks does not qualify this task.

Packet retrieval is prepared once per case/budget/encoding and reused across seeds. Saved
`retrieval_seconds` values are shared measurements, including SQLite reads, serialization, and
token checks. They exclude inference/network/client overhead and are not independent repeated
speed samples. Reader wall/input/output costs are separately recorded per actual call. No speed
claim follows from shorter packets alone.

## Reproduce

```sh
uv sync --locked
ollama pull qwen3:8b
uv run compactionlab prepare-tokenizer --model qwen3:8b
uv run compactionlab replay \
  --source results/token-budget-2026-10-01/1b62ebbc316d.json \
  --budgets 128 256 384 512 --seeds 42 43 44
```

The frozen writer output is already public, so no 4B download is needed for replay.
Local results appear under `.local/runs` and in the dashboard. All errors and raw requests,
answers, contexts, model/tokenizer/source hashes and runtime costs are retained.
Different devices/runtime revisions may produce different outputs; calibrate their tokenizer
and record the changed manifest. Encoding fidelity and historical-budget enforcement are
covered by offline tests that require no inference, downloads or account credentials.
