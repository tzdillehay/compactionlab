# Roadmap

## Implemented first slice

Local versioned memory store, atomic writes, lexical retrieval, source/dependency relationships,
HTTP/MCP interfaces, comparison dashboard, real local model calls and three state-probe tasks.
This deliberately narrows the larger proposed study to something reviewable and runnable.

Version 0.2 implements the first research batch: configurable inference, prepared/calibrated Qwen
token counters, historical-token allowances, and parameterized receiver qualification with
full-history/minimal-source controls and a deterministic draft calculator. This qualifies declared
state reconstruction only; actual tool execution remains a later gate. See [protocol](qualification.md).

The follow-up `representation-v1` study freezes the same model-written graph and compares
verbose packets, compact shared-source packets, a fixed-selection encoding control, recent
history, and full history across four allowances and three seeds. It finds partial factual
gains and a strict conversation regression, without a complete-task gain from compact encoding.
See [measured findings](representation-findings.md). Source-priority retrieval and unfinished
obligations now deserve testing before further packet-size optimization.

## Next controlled study

1. Separate fact provenance from completion evidence explicitly in the output schema. Requalify
   models on independent templates before freezing checkpoints and policies; retain this batch's
   original grades. A stricter format failure does not by itself establish failed recall.
2. Extend calibrated preflight to writers, then target-tokenizer budgets to long histories,
   repeated compactions, and separate
   retrieval/tool costs. Compare compact source spans with verbose record metadata under the same
   historical allowance, reporting total inference and memory-building cost separately.
   First compare source-aware ranking with current lexical ranking on new correction/no-change
   pairs, preserving the encoding controls and a recent-event baseline. Measure factual recall,
   unfinished actions and unsafe completion claims separately. Stronger readers and a second
   model family should use paired full-source controls; changing receivers changes the study.
3. Compare stronger existing external-memory systems through adapters; cite their mechanisms.
4. Add true app-building continuations in disposable sandboxes with independent acceptance tests.
5. Extend conversation, research, project planning, and fully specified multi-period debt snowball
   tasks, with correction/no-change pairs and independent templates.
6. Study automatic capture versus explicit client writes, recurring compaction, and both model
   handoff directions. Distinguish extraction omission, retrieval miss and reader misuse.
7. Add relationship/status/source ablations and measure latency with warm/cold loading separated.
8. Explore Jev or another decision model as a retrieval reranker while freezing the memory store
   and receiving model. This is optional and requires separate authorization for paid access.

External validation candidates include [LongMemEval](https://github.com/xiaowu0162/LongMemEval)
and [LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2). They are related work and possible
future adapters, not measurements performed by this prototype. The latter's public harness includes
an API-based judge; running that judge would require the user's cost authorization.

The design hypothesis is that preserving state and evidence scope improves continuity. The
prototype does not establish it. External memory and temporal graphs are established prior work.
