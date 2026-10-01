# First experiment: state reconstruction across model handoffs

Protocol: `state-probe-v3`. This is a functional pilot, not the broader CompactionLab evaluation.

The frozen first matrix uses one repetition, all three cases and five conditions for each of:
4B→8B, 8B→4B, 4B→4B and 8B→8B at 6000 bytes; plus both cross-model directions at 2000 bytes.
That is 90 planned probes. `scripts/run_smoke.py` runs exactly this matrix. The 6000-byte
same-model conditions are controls; they are not repeated at 2000 bytes in this small pilot.

## Question

After a requirement correction or artifact change, does a fresh receiving model recover current
facts, necessary next actions and the scope of existing evidence from an external memory store?

## Tasks and independent grading

1. **Release handoff:** a small Python shipping function at revision A has two real passing
   assertions. The user changes the free-shipping threshold from 5000 to 7500 cents. The
   implementation becomes revision B, but old assertions remain and no B test run occurs.
   The receiver must recall the 7500 threshold and 499 fee, identify B validation as pending,
   plan both updating and rerunning tests, and avoid claiming completion or using A's test log
   as proof of B. The fixture actually executes A assertions in a disposable directory.
2. **Conversation:** user corrections replace email with SMS and move a delivery date. An
   assistant approval guess is contradicted by the user. The receiver must preserve the new
   contact/date and ask for the unconfirmed address without scheduling an unapproved delivery.
3. **Budget:** entirely synthetic debts, integer cents, zero interest for one month. The user
   lowers a total payment budget from 120000 to 90000 cents. Minimums total 50000 and the extra
   40000 goes to Pine, yielding Pine 50000, Oak 25000, Cedar 15000. A separate reference
   calculator applies minimums, balance caps, ascending balance order and name tie-breaks.
   Draft computation is not payment approval or execution.

These are declared JSON state probes. No receiving model actually modifies the app, schedules a
delivery or executes payments. `complete=false` alone is not a pass; all facts and required actions
must be correct. Evidence fields are deliberately scoped to current completion, so they must be
empty at these checkpoints. Ground truth is not placed in model requests. It is publicly
inspectable source code, so these fixtures are development cases, not an uncontaminated test set.

## Conditions and pairing

For each case/repetition, a frozen writer model sees the same visible event history twice: once
to produce an ordinary handoff summary, once to propose structured memory records. The record
writer is not given the receiving query or grader. Both plain and structured methods use the
same extracted records. No record is repaired from ground truth. Extraction/validation errors
are preserved and mark affected conditions as unavailable.

The first development run used `state-probe-v1`. It exposed confusion between event IDs and
source roles, and prose mixed into numeric output fields. Version 2 constrains source references
to the visible event IDs, numeric fields to integer strings or unknown, and action IDs to the
public task interface, with descriptions. These are output-contract changes, not supplied answers.
The initial run is retained separately and must not be pooled with v2 results. Graders and task
histories are unchanged. V2 is still a development protocol, not a held-out evaluation.

Version 3 also defines categorical field vocabularies (for example address_confirmation versus
approval_confirmation) instead of relying on exact matching of unrestricted prose. Every possible
category remains available regardless of memory condition. This avoids scoring equivalent phrases
as different states; no correct category is supplied. V1 and V2 development runs are retained
separately. V3 comparisons are frozen for the first smoke report, not a statistical evaluation.

The same receiving model answers five fresh requests:

| Condition | Historical input |
| --- | --- |
| Full history | Entire source event sequence, uncompressed reference |
| Recent history | Contiguous suffix of whole events within the ceiling |
| Summary | The writer's bounded ordinary summary |
| Plain | Scoped lexical retrieval of compact record text |
| Structured | Same search with supersession filtering, dependencies and source evidence |

Current request, system prompt, allowed actions, fact fields, sampling and generation limit are
identical across conditions. Compressed histories use the same UTF-8 byte ceiling. Metadata and
source bodies count toward it. This is **not a token-matched experiment**: actual prompt and
output token counts are recorded but token allocation varies. At 6000 bytes, several small
histories fit entirely in recent history, making that condition a useful equivalence check rather
than a difficult compression task.

Default models are Qwen3 4B/8B Q4_K_M through Ollama, with `think=false`, temperature 0.7,
top_p 0.8, top_k 20, num_ctx 8192, num_predict 2048, seed 42+repetition. Seeds do not guarantee
identical generations across different prompts. Digests, template hash, runtime version,
requests, raw responses and timing are saved. There are no automatic retries, hidden repairs or
paid APIs. Model-assisted memory creation cost is recorded separately from continuation cost.

Run both 4B→8B and 8B→4B, plus 4B→4B and 8B→8B controls. Interpret method differences within a
fixed receiving model; a difference between 4B and 8B receivers is not a memory effect. Each
condition's order is shuffled with a recorded seed. Models run sequentially and the local Ollama
setup loads at most one model at a time.

## Outputs and interpretation

JSON results contain every planned trial, graded outcomes, writer errors and backend errors.
Errors are distinct from model correctness failures and are included in coverage denominators.
Metrics are strict pass counts, per-field accuracy, failed checks, context bytes, actual tokens,
wall time and backend-reported loading/inference time. Strict pass counts combine truthfulness
and state reconstruction, not autonomous task completion.

Three templates and a few samples cannot support statistical superiority claims. Repetitions
share histories/templates and are not independent new tasks. These tasks are intentionally
short and may produce ceiling effects. Negative results are retained. Larger independent tasks,
token-matched allowances, writer ablations, true tool continuations, and adversarial source
handling are prerequisites for stronger claims.
