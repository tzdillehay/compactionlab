# Receiver qualification and token accounting

This first research batch adds configurable inference, `qualification-v3`, and
`state-probe-v4`. The published v3 smoke traces are unchanged and must not be pooled with v4.

## Prepare a tokenizer

```sh
uv run compactionlab prepare-tokenizer --model qwen3:8b
```

This explicit preparation command downloads tokenizer JSON from the official Qwen Hugging Face
repository at a resolved immutable revision. It records its SHA-256, model digest, runtime
version and chat-template hash. It checks three raw tokenization probes, including Unicode and
JSON, and two chat-rendering probes with thinking disabled/enabled against Ollama's reported
input token count. Preparation requires internet and local inference; evaluation has no downloads.

Support initially covers official `qwen3:4b`, `qwen3:8b`, and `qwen3:14b` names. A runtime/model
change or tokenizer integrity failure requires preparation again. The calibrated chat renderer
supports the runner's single system/user turn, with no images or native tool messages. It is not
a general renderer for every model or client conversation. Every subsequent token-accounted
generation checks its predicted input count against the runtime; a mismatch is a retained error.

## Capability calibration

```sh
uv run compactionlab qualify --model qwen3:8b --cases-per-workflow 20
uv run compactionlab qualify --model qwen3:8b --cases-per-workflow 20 \
  --thinking --output-tokens 6144
```

Twenty parameterized cases in each of three workflows are evaluated with full history and an
annotated subset of original source events containing the needed current information. The
subset is a diagnostic oracle control, not a competing memory method. It is assembled from
case-generation annotations, not an LLM summary. Neither condition receives grader fields.

Cases vary values, completion state, correction state and remaining actions. Shipping fixtures
actually execute boundary assertions at the relevant revision. Delivery/payment receipts are
explicitly simulated fixture events. The receiver reconstructs declared state; it does not build
an application, schedule a real delivery, or execute a payment. These shared-template calibration
cases are development data, not a diverse held-out benchmark or proof of autonomous competence.

For budgeting, the default calculator supplies a deterministic draft observation to both
conditions from the same visible account/budget inputs. This isolates arithmetic while retaining
approval/execution distinctions. The calculator implementation is independent of the reference
grader and cross-checked in offline tests. The runner supplies its input; this does not test
whether a model can choose a tool or extract its arguments. Use `--no-calculator` for that aided
versus unaided state-probe comparison, keeping other settings fixed.

Strict success requires all facts, required actions, correct completion state and current
completion evidence. Completed tasks may have no remaining action. Required current tool
observations must be cited; additional relevant current source references are allowed. A stale
test or assistant completion assertion does not substitute for a current test observation.

A workflow qualifies with at least 20 full-history trials and at least 90% strict success,
counting errors as failures. Minimal-source success cannot qualify a model. A four-case smoke
can exercise each branch but cannot qualify a model, even if every answer passes. Qualification
is an operational screening rule for these tasks, not a statistical superiority claim.

The initial `qualification-v1` development smoke required an exact evidence-ID list, rejecting
some legitimate supporting artifact/user references; it also required declaring completion
as a next action when no work remained. V2 corrects those grading contracts and prohibits
repeating executed payments. The development trace is retained separately with its original
grades. V2's larger development run also rejected a truthful unchanged-revision assistant
recap even when the mandatory test observation was cited. V3 allows that redundant current
reference while still requiring the tool observation and rejecting stale revision references.
Both development runs retain their original grades, separate from the frozen v3 study.

## Inference configuration

Writer and reader settings are separate in comparison requests. Qualification uses one settings
object. Configurable values include thinking, context capacity, output allowance, temperature
and top-p. Defaults preserve the pilot's non-thinking sampling: temperature 0.7, top-p 0.8,
top-k 20. Thinking defaults use temperature 0.6 and top-p 0.95, following Qwen's model card.
Explicit sampling overrides are recorded. Comparisons must freeze a selected configuration;
changing the thinking mode and sampling together is a configuration comparison, not an isolated
causal estimate of thinking alone.

Both modes store raw responses, including returned thinking text, output token counts and
duration. Runtime output tokens include reasoning when returned by the backend; no separate
reasoning-token count is inferred. Length cutoffs, capacity violations, accounting mismatches,
schema failures and backend failures are retained without retries or repair. Calibrated input
plus the configured output reserve must fit the context capacity before inference starts.

Calibrated preflight and rendered-input audits apply to qualification calls and to receiver calls
in token-mode comparisons. Comparison writers retain runtime-reported costs, but do not yet use
calibrated input preflight. The current writer fixtures are short; longer-history studies must add
writer preflight before treating extraction failures as compaction failures.

## Historical token allowances

```sh
uv run compactionlab evaluate --writer qwen3:4b --reader qwen3:8b \
  --token-budget 512 --cases release_handoff
```

With `--token-budget`, the bounded unit is the **serialized JSON string value of
`historical_context`**, including its quotes and escaping. Metadata, source text and
relationships in that value count. Recent history admits a contiguous suffix of whole events;
record retrieval admits entire dependency groups; over-budget summaries are retained as writer
errors. No string is truncated in the middle. Token mode replaces the historical byte ceiling.
Full history remains an unbounded historical reference, subject to actual runtime capacity.
The dashboard also offers a 128-token engineering stress smoke: the original short histories
exceed that allowance, but this is still not a long-horizon compaction benchmark.

This is an equal historical-token allowance, not an equal total input or output cost. System
instructions, current request, output contract and chat-template overhead are separately visible;
actual full prompt tokens are checked/recorded. Text token counts are tokenizer-defined and can
differ at surrounding-text boundaries, which is why the full rendered prompt is also audited.
No tool/evidence-fetch loop exists in this batch; accounting for it is required before adding one.

Results persist in `.local/qualifications/` and `.local/runs/`. HTTP and CLI use the same
cross-process experiment lock. The dashboard offers the new controls and qualification results.
Offline quality checks require no tokenizer download or running inference service.

## References

- [Qwen3 8B model card](https://huggingface.co/Qwen/Qwen3-8B): thinking modes and sampling.
- [Official tokenizer files](https://huggingface.co/Qwen/Qwen3-8B/tree/main).
- [Ollama thinking API](https://docs.ollama.com/capabilities/thinking).

Next: qualify a receiving configuration, then build long histories, compact source-span memory,
repeated compaction and actual tool continuations as described in the roadmap.
