# Task-state retrieval: measured development results

Current-state selection preserved **100% of the three requested facts**, compared with 72.5%
for lexical retrieval, 51.7% for recent history, and 61.7% for model summaries. Linked current
state achieved 15/40 behavior passes and 13/40 strict passes. This supports testing correctly
recorded current-state filtering further; it does not establish reliable workflow continuation.

Frozen protocol: [lifecycle-v1](../../docs/lifecycle.md). Source was committed before model inference at
[da4b6e6](https://github.com/tzdillehay/compactionlab/tree/da4b6e6eec4d43215fb4d9162a2302747ac5bafc).
Run `58063e74e7c6` contains 40 summary calls and 280 fresh receiving-model probes. Complete
[synthetic trace](58063e74e7c6.json), [pre-inference packet check](preflight.json), and [hash manifest](manifest.json).

Four workflow templates (release, conversation, budget review, research), five lifecycle states,
and old/recent event placement. These are 40 controlled checkpoints, not 40 independent tasks.
Explicit typed application callbacks are assumed accurate. Receipts are SIMULATED; no real
release, delivery, budget execution or communication occurred. Automatic memory extraction
and cross-family model transfer are not tested. Default HTTP/MCP retrieval is unchanged.

Qwen3 8B, thinking off, one seed (314159), 8,192 context and 2,048 output reserve; Apple M5 Pro,
24 GiB unified memory, GPU inference. Five methods have a 512-historical-token ceiling;
full-history and oracle minimal-source controls have no historical ceiling. Shared prompt,
schema, event encoding and shuffled receiver order. All non-summary packets were frozen first.

## All-case outcomes

| Method | Behavior passes | Strict passes | Fact accuracy | Missed action cases | Extra action cases | Repeated completed actions | False completion cases | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| full_history | 8/40 | 6/40 | 98.3% | 24 | 0 | 0 | 20 | 0 |
| minimal_source | 12/40 | 12/40 | 100.0% | 18 | 0 | 0 | 8 | 0 |
| recent_history | 4/40 | 3/40 | 51.7% | 21 | 0 | 0 | 13 | 0 |
| summary | 3/40 | 0/40 | 61.7% | 18 | 4 | 0 | 6 | 0 |
| lexical | 4/40 | 0/40 | 72.5% | 24 | 0 | 0 | 22 | 0 |
| current_no_links | 16/40 | 14/40 | 100.0% | 11 | 0 | 0 | 7 | 0 |
| linked_current | 15/40 | 13/40 | 100.0% | 11 | 0 | 0 | 7 | 0 |

Behavior success requires all current facts, exact ready actions, exact current completed actions,
and honest workflow completion. Strict success also requires current fact provenance and the
right current completion receipts. Counts are affected responses, not action counts. Errors stay
in the denominator. Fact accuracy averages three fact checks per graded response.

## Paired behavior comparisons

Both full-history and minimal-source controls pass behavior in **8/40** checkpoints.
This predeclared diagnostic subset is reported alongside all cases; it is not independent receiver
qualification. Excluded case IDs remain in `analysis.control_excluded_cases` in the complete trace.

| Linked current state vs | All cases: wins / losses / ties | Control-supported: wins / losses / ties |
|---|---:|---:|
| lexical | 11 / 0 / 29 | 4 / 0 / 4 |
| recent_history | 11 / 0 / 29 | 4 / 0 / 4 |
| summary | 12 / 0 / 28 | 5 / 0 / 3 |
| current_no_links | 0 / 1 / 39 | 0 / 0 / 8 |

Strict paired comparisons and workflow/state/placement breakdowns are saved in `analysis`.
Wins are paired binary behavior changes, not a significance test. One seed and four templates
do not establish general superiority.

## Input parity and generation variation

Linked and no-links methods have identical packets and complete request payloads in **40/40**
pairs. Both already fit the current goal, constraint and two task states at this allowance.
This run cannot demonstrate a separate dependency-expansion benefit.
Identical seeded requests yielded different parsed answers in 1/40 pairs; behavior scores differed
in 1/40 and strict scores in 1/40. These differences are generation variation,
not a retrieval-policy effect. Exact IDs are retained in the manifest.

## Cost and accounting

| Method | History tokens (min–max) | Median receiver wall seconds |
|---|---:|---:|
| full_history | 1785–2303 | 4.827 |
| minimal_source | 218–292 | 2.610 |
| recent_history | 466–509 | 3.083 |
| summary | 61–145 | 2.318 |
| lexical | 468–512 | 2.946 |
| current_no_links | 467–512 | 2.817 |
| linked_current | 467–512 | 3.024 |

Summary construction adds 154.29 wall seconds and
80,166 input / 4,021 output tokens,
separate from the receiver table. Summary prefix truncation affected 0/40 cases.
All 320/320 model-call input audits match the calibrated runtime. Total run wall time:
1025.38 seconds. No backend, capacity or output errors occurred.
Timing is descriptive: one machine, sequential calls, shared packet preparation, cache and
warm-up effects. Retrieval/database latency was not independently timed; do not claim a
memory recall speed improvement from this table.

## State and placement breakdown

| Dimension | Value | Linked behavior | Linked strict | Recent behavior | Summary behavior | Lexical behavior |
|---|---|---:|---:|---:|---:|---:|
| workflow | conversation | 4/10 | 3/10 | 1/10 | 1/10 | 0/10 |
| workflow | release_handoff | 5/10 | 4/10 | 1/10 | 0/10 | 2/10 |
| workflow | research | 3/10 | 3/10 | 1/10 | 2/10 | 1/10 |
| workflow | budgeting | 3/10 | 3/10 | 1/10 | 0/10 | 1/10 |
| checkpoint | followup_pending | 1/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| checkpoint | pending | 0/8 | 0/8 | 0/8 | 0/8 | 0/8 |
| checkpoint | canceled | 1/8 | 1/8 | 0/8 | 0/8 | 0/8 |
| checkpoint | reopened | 5/8 | 5/8 | 0/8 | 0/8 | 0/8 |
| checkpoint | completed | 8/8 | 7/8 | 4/8 | 3/8 | 4/8 |
| placement | old | 9/20 | 8/20 | 0/20 | 2/20 | 2/20 |
| placement | recent | 6/20 | 5/20 | 4/20 | 1/20 | 2/20 |

## What improved, what remains broken

The source-aware current-head filter, task priority and bounded selection operate together.
This run does not isolate their individual contributions. The preflight found the required
current fact sources in 40/40 current-state packets, 20/40 recent packets and 15/40 lexical
packets. The longer neutral notes deliberately pressure recency and query overlap; this is a
controlled stress fixture, not a naturally sampled conversation corpus.

The completed-workflow controls support an observed behavior gain: linked state passes all
8 completed checkpoints, versus 4/8 for recent and lexical retrieval and 3/8 for summaries.
The remaining states fail at least one behavior control. Their descriptive gains and failures
remain visible, but do not establish a retrieval-only explanation. Linked state does better
on reopened cases (5/8), yet pending tasks score 0/8, canceled tasks 1/8, and unfinished
follow-ups 1/8. Repetition of completed actions is 0 in every method, so this batch does not
establish an improvement on that metric.

For example, `conversation-followup_pending-old` contains a completed address confirmation
and a still-pending delivery follow-up. Linked retrieval returns the correct current facts
and the ready `schedule_delivery` action, but the model also says `complete: true` and cites
only the address-confirmation receipt. Full history misses that ready follow-up and also
claims completion. Preserving memory alone did not make the workflow-completion decision correct.

Linked state has 11 strict wins, one strict loss and 28 ties against recent history across all
cases. The strict loss is a citation failure, not a loss of requested facts. Full-history
controls have 98.3% factual accuracy but only 8/40 behavior passes, including 20 false completion
claims. The reader needs a better state-to-action interface or stronger capability in addition
to better retrieval. No hardware-capacity failure explains these observations.

## Next hypothesis

Compare these same raw current-state packets with a model-independent derived view that explicitly
computes ready actions, blocked tasks, current completed actions and workflow completion from
source events and same-revision dependencies. Keep it derived from supplied state, never from
fixture truth annotations. Verify the state engine against independent state-transition tests.
Freeze a new protocol and pair both inputs with full/minimal controls across repeated seeds.
Measure whether this removes missed follow-ups and false completion without hiding conflicting
or unsupported state. A stronger receiver/second model family is a separate capability comparison.

After a state engine helps with reliable callbacks, test automatic free-form extraction and
missing/conflicting events separately. Real agent execution and repeated cross-model handoffs
remain later steps. These measurements are a development study, not a broad benchmark claim.
