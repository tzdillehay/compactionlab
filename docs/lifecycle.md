# Task-state retrieval: lifecycle-v1

Development hypothesis: retrieving authoritative current task heads and their causal dependencies
reduces repeated completed actions, missed follow-ups, and false completion relative to lexical
matching, a recent-event suffix, or a flat model summary.

This protocol, fixtures, policies, schemas, and grader are committed before inference. No tuning
after observing receiving-model answers is allowed within this run. Preserve failures and publish
the complete trace. Any subsequent policy change starts a different frozen run.

## Inputs and scope

Forty checkpoints: four workflows (app release, conversation/delivery, budget review, research),
five task states (pending, completed, canceled, reopened after a requirement correction, primary
completed with a follow-up pending), and two placements (important history before/after 32 neutral
notes). Old/recent cases have identical event content and truth; only note placement changes.
Each state/placement is a controlled variation of one workflow template, not an independent task.
The same numeric/text requirements recur within a workflow to make state contrasts interpretable.

Every input is an explicit typed user/tool event, with source, entity, revision, status, action,
dependency entities, replacement event IDs, and a short description. Assistant guesses are retained.
Fixtures model reliable application callbacks; receipts are SIMULATED. Nothing schedules delivery,
publishes an app, transfers money, or sends a brief. Budgeting probes workflow state and its stated
allowance, not snowball arithmetic. Free-form memory extraction and corrupted/missing callback
recovery are outside this experiment. This measures the value of correctly recorded state, not
whether a model can build that state correctly. External task ledgers and graphs are established
engineering patterns; this is not a novelty claim.

The ledger is persisted through the existing append-only SQLite service and read back before
retrieval. The transport-independent typed records are carried in record text. The existing
MemoryRecord status vocabulary is unchanged; canceled study records map to uncertain there,
while their typed payload retains the explicit canceled state. This adapter is a research slice,
not a complete account-backed product or a change to the default HTTP/MCP retrieval policy.

## Frozen comparison

Qwen3 8B receiver, thinking disabled, seed 314159, 8192 context / 2048 output reserve, native
calibrated tokenizer and complete input audits. A 512-historical-token ceiling applies to:

1. `recent_history`: contiguous suffix of the same typed ledger.
2. `summary`: one full-ledger 8B summary per case, separately charged; truncate its prefix to fit.
3. `lexical`: distinct-word overlap with the request, then recency, like the existing lexical policy.
4. `current_no_links`: authoritative current entity heads, actionable task priority, no dependency expansion.
5. `linked_current`: identical ranking and encoding, with atomic same-revision dependency expansion.

Two ceiling-free controls: `full_history`, and `minimal_source` (a fixture-selected oracle diagnostic,
never used by either retrieval policy). The receiving prompt, schema, sampling settings and seed
are identical across conditions for each case. Packets preserve original record fields and are
serialized chronologically, so identical selected sets produce identical inputs. Links resolve
current entities at the same revision; an old receipt cannot satisfy a reopened task.

All non-summary packets are frozen before writer calls. Summaries cannot access truth annotations.
Writer failures remain planned reader failures without a substitute summary. Shuffle reader order
across workflows, placements and methods. Forty summary calls and 280 receiving probes are planned.
No automatic repair, retries, paid calls, or follow-on larger-model downloads occur.

## Outcomes

Primary behavior: current facts, exact ready next actions, exact current completed actions, and
honest workflow completion. Track missed actions, extra actions, repetitions of completed actions,
and false completion separately. A blocked second stage is not a ready action; a canceled workflow
is not successfully complete. Full completion requires both current stages' tool receipts.

Strict pass also requires current fact provenance and current completion evidence. These are
separate fields; a fact source need not prove workflow completion. Report behavior success alongside
strict success so citation failures cannot be mislabeled as lost factual memory.

Report all 40 cases, plus a predeclared control-supported diagnostic subset where BOTH full-history
and minimal-source controls pass the behavior contract. Its size and all excluded cases remain
visible. This is not the older >=20-case receiver qualification gate. Compare methods paired by
checkpoint, report wins/losses/ties, and break down workflow, state and placement. With one seed and
four templates, do not claim statistical significance or general superiority. Preserve direct
packet parity for the no-links ablation; if inputs coincide, it cannot demonstrate a link benefit.

Token/byte counts, writer and reader wall time, load/prompt/inference time and input accounting
are retained. Packet preparation is shared across conditions/seeds; it is not an independent
retrieval-speed experiment. A stronger reader/second family is a separate controlled run.

```sh
uv run compactionlab prepare-tokenizer --model qwen3:8b
uv run compactionlab lifecycle --reader qwen3:8b --token-budget 512 --seed 314159
```

## Pre-inference packet check

The native tokenizer preflight found 1,785–2,303 historical tokens per full ledger and 218–292
in the oracle minimal-source packets. Largest complete receiver input: 2,571 tokens; largest
summary input: 2,295 tokens, both within the 8,192 context with 2,048 output reserve.
Both current-state policies contain the required current fact source IDs in 40/40 packets;
recent suffix does so in 20/40 and lexical retrieval in 15/40. This is packet coverage, not
measured receiving-model accuracy. At 512 tokens, current_no_links and linked_current have
identical inputs in all 40 cases. Therefore this run cannot isolate a dependency-expansion
benefit. Keep the planned ablation and report input parity; do not count equal inputs as
independent evidence for links. No model inference was used in this check.
