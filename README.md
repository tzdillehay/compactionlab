# CompactionLab

**Portable context memory, with reproducible tests of what survives a model handoff.**

CompactionLab is a small local service that stores sourced, versioned task records outside an LLM.
An HTTP API and an MCP server let different clients retrieve the same project state. A local
dashboard inspects records and compares fresh model continuations using full history, recent
history, an LLM summary, plain records, and records with state/evidence relationships.

This is an engineering prototype and a state-reconstruction smoke study, not a published benchmark
result or a claim that external memory is new. Models can extract incorrect records, misjudge
supersession, or misuse correct context. See [experiment protocol](docs/experiment.md) and
[architecture](docs/architecture.md).

[Initial measured results](results/smoke-2026-10-01/README.md): 90 frozen state probes across both
handoff directions, same-model controls and two byte ceilings. Structured memory has not established
an advantage. Receiver capability, extraction errors and metadata overhead remain visible failure
sources. Raw traces and earlier unsuccessful contract-development runs are included.

Version 0.2 adds receiver qualification, independently configurable writer/reader reasoning,
and calibrated historical-token allowances. See [qualification protocol](docs/qualification.md).
These new development studies are separate from the original byte-bounded smoke.
The [240-probe qualification report](results/qualification-2026-10-01/README.md) separates
factual accuracy from the completion-evidence contract. The
[token-accounting stress smoke](results/token-budget-2026-10-01/README.md) checks real historical
allowance enforcement through the dashboard; it does not establish a memory-method advantage.
The current runner emits `state-probe-v4`. To reproduce the original v3 protocol, use the
[frozen v0.1 source](https://github.com/tzdillehay/compactionlab/tree/ea70abf280a5ad513efe3147e602102df4346cd4).

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[Ollama](https://ollama.com/download), then:

```sh
git clone https://github.com/tzdillehay/compactionlab.git
cd compactionlab
uv sync --locked
ollama pull qwen3:4b
ollama pull qwen3:8b
# Run `ollama serve` in another terminal if Ollama is not already running.
uv run compactionlab serve
```

Open **http://127.0.0.1:8765**. The service binds to loopback and the dashboard uses no CDN.
Select installed writer/reader models, run a comparison, and inspect each context and response.
No API key or paid model is required. Pulling weights requires several GB of disk space.

Python 3.12+; macOS Apple Silicon is the initial inference target. Offline checks run on Linux and
Windows in CI. Windows GPU inference has not been measured by this project.

## Qualify a receiver and count tokens

```sh
uv run compactionlab prepare-tokenizer --model qwen3:8b
uv run compactionlab qualify --model qwen3:8b --cases-per-workflow 20
uv run compactionlab qualify --model qwen3:8b --cases-per-workflow 20 \
  --thinking --output-tokens 6144
uv run compactionlab evaluate --reader qwen3:8b --token-budget 512
```

Tokenizer preparation explicitly downloads official tokenizer data and calibrates it against the
installed model/runtime. Evaluation downloads nothing. Qualification compares full history with
an annotated source subset, includes both completed and unfinished tasks, and supplies the same
budget calculator to both conditions. At least 20 full-history cases per workflow and 90% strict
success are required; errors count as failures. These are parameterized state probes, not actual
agent execution. The dashboard exposes qualification, thinking and token-allowance controls.

Token budgets count the serialized historical context, including metadata and escaping. Full
prompt token counts are audited against the runtime. Model/template changes fail closed until
recalibration. This supported Qwen chat renderer is not a general tokenizer for every LLM.

## Run the test without the interface

```sh
uv run compactionlab evaluate --writer qwen3:4b --reader qwen3:8b --repetitions 1
uv run compactionlab evaluate --writer qwen3:8b --reader qwen3:4b --repetitions 1
uv run compactionlab evaluate --writer qwen3:4b --reader qwen3:4b --repetitions 1
uv run python scripts/run_smoke.py
```

Each run saves JSON with the visible histories, model-written memories, supplied context, raw
responses, deterministic grading, model digests, inference settings, tokens, and latency in
`.local/runs/`. One writer generates a summary and structured records from the same visible
history. Each reader condition starts a fresh conversation. The grader is never included in the
model request. Failed extraction and backend errors remain visible.

The initial cases are release handoff, conversation corrections, and a synthetic one-period debt
snowball budget. The release case captures a real passing test log for revision A before creating
revision B. Its continuation is a **declared state probe**, not an autonomous app implementation.

## Use the external context service

```sh
curl http://127.0.0.1:8765/api/namespaces
```

API reference and OpenAPI schema: **http://127.0.0.1:8765/docs**. Writes require an expected revision;
record IDs and source events are immutable. Corrections append records with `supersedes` links.
Each namespace is a separate project/task scope, not an authentication boundary.

For an MCP-compatible client, configure this stdio server (substitute your absolute checkout path):

```json
{
  "mcpServers": {
    "compactionlab": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/compactionlab",
        "run",
        "compactionlab",
        "mcp"
      ]
    }
  }
}
```

HTTP and MCP share `.local/memory.sqlite3` by default. Set `COMPACTIONLAB_DATA_DIR` to an absolute
path to share a store across launch directories. A host must call memory tools or inject retrieved
context; the server cannot automatically see a client's hidden history. Retrieved bytes still
consume the receiving model's input tokens.

## Quality and reproduction

```sh
uv run python scripts/quality.py
uv build
```

Quality checks require no running model, credentials, or model download. They cover transactions,
conflicts, source references, dependency closure, isolation, retrieval bounds, API errors, actual
MCP client/server round trips, and grader negative cases. CI uses the lockfile.

The smoke test uses equal **UTF-8 byte ceilings**, not equal model token budgets. Actual token counts
are recorded. Full history is an uncompressed reference. Small samples, shared templates, and
changing hardware load limit interpretation; a passing example does not establish superiority.
The wider controlled study is planned separately in [roadmap](docs/roadmap.md).

## Related work

External memory is established work: [MemGPT / Letta](https://www.letta.com/blog/memory-blocks/),
[Mem0](https://github.com/mem0ai/mem0), and
[Graphiti / Zep](https://github.com/getzep/graphiti). CompactionLab's focus is an inspectable
evaluation of evolving state, evidence scope, and model handoffs. We do not claim research novelty.
See [references](docs/references.md).

Original code and synthetic fixtures: Apache-2.0. Model weights and dependencies retain their own
licenses. No model weights, private histories, credentials, or local database are committed.
