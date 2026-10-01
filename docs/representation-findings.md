# What the encoding sweep tells us

These observations refer only to frozen run `18fbde355da7`: three known synthetic checkpoints,
four historical allowances, three seeds, Qwen3 4B's previously written memory, and an 8B receiver
with reasoning disabled. The [report](../results/representation-2026-10-01/README.md) retains all
153 calls and costs. The [protocol](representation.md) was frozen before receiving-model inference.
This development study does not establish general superiority or statistical significance.

## Improvement worth preserving

At 384 tokens, compact selection retains `accounts` and `budget-current`; verbose selection
retains `accounts` and the chart-color `note`. Compact receiving calls get **6/7 fact fields
correct**, versus **3/7** with verbose packets, for all three seeds. They recover the corrected
90000-cent allowance, 50000-cent minimum total, and 40000-cent extra amount. They still fail to
apply that extra to Pine's payment and fail the action/completion contract.

Every fresh full-history budget reference also fails. This is useful evidence about partial
recall, not evidence of a working budget agent or qualification of the receiver. The previous
calculator-aided qualification is a different task. Preserve fact-level measurements alongside
strict task outcomes so a partial gain remains visible without being overstated.

The fixed-selection compact format reduces historical token counts by approximately **7.5–21.5%**
across the twelve case/allowance combinations while reconstructing exactly the same selected
records. This is a representation-size improvement. It produces no strict-pass change and does
not establish a latency improvement.

## Regression worth avoiding

At 384 tokens, conversation recall is **3/3 strict passes** for verbose packets and **2/3** for
adaptive compact packets. Compact selection contains the old assistant `approval-guess` where
verbose selection contains the brief-style preference. On seed 43, the compact receiver returns
`approval_confirmation` instead of `address_confirmation`, despite correctly returning SMS,
the corrected deadline, and unapproved status. Its next action is still `ask_address`.

The compact fixed-selection control passes **3/3**, preserving the verbose record set. This
supports investigating selection/content differences. It does not isolate the stale approval
claim as the cause: the removed style record, source-table composition, and resulting sampling
also differ. A follow-up must intervene on these individually before claiming causality.

Compact encoding produces **zero strict-pass wins and one regression** across the 36 pairs
against verbose encoding. More stored context admitted under an allowance is not automatically
better recall. Treating this as a favorable aggregate result would hide the most useful failure.

## The simplest baseline remains strong

Recent source history passes every release and conversation trial at all four allowances:
**24/24**, versus verbose **6/24** and compact **5/24** on those two workflows. These are twelve
repeats per workflow, not twelve independent tasks. All fresh full-history references for these
two workflows pass. The source histories contain only 156–323 tokens; even the 128-token suffix
retains the important recent corrections and obligations. This does not generalize to old facts
outside that suffix or long-running workflows.

At 384/512 tokens, every structured release call recalls all four fact fields correctly but
omits `update_tests`, returning only `run_tests`. At 512, the selected artifact explicitly says
the assertions still belong to revision A. This is an obligation/action failure even when the
necessary fact is visible, not simply missing memory. No actual code action was executed by a
receiver in this study.

## Next experiment

Freeze a new development protocol before inference. Compare current lexical ranking with a
source-aware policy that prioritizes recent user corrections, observed tool results, and explicit
unfinished obligations over unsupported assistant claims. Keep historical records inspectable;
do not rewrite the writer's mistakes or use grade annotations during retrieval.

Use independent correction/no-change pairs in which the important event is sometimes old and
sometimes recent, plus matched neutral distractors. Keep full-source, recent-event, same-selection
encoding and minimal-source diagnostic controls. Separately ablate the conversation's approval
guess and style record to test the observed regression. Keep fact accuracy, required actions,
completion claims, extraction fidelity and retrieval coverage separate.

For arithmetic, provide an identical explicit calculator observation to every condition or
qualify a stronger receiver on the unaided task first. Do not change the budget aid midway or
merge its results into this frozen study. Run the same memories with a second model family to
test portability beyond Qwen sizes, with fresh full-source controls and native token accounting.

No hardware capacity failure occurred on this Mac. All 153 full-input audits matched, with zero
backend, capacity or output errors. The RTX 5080 workstation can support a separate larger-model
comparison when needed; Windows GPU inference has not yet been measured here. Current failures
justify retrieval and receiver-capability experiments, not an assumption that the hardware failed.
