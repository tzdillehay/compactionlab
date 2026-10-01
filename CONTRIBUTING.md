# Contributing

Run `uv sync --locked` and `uv run python scripts/quality.py` before submitting changes.
Keep offline checks independent of credentials and model downloads. Add regression coverage for
changes to storage, retrieval, grading or trial isolation.

Changing prompts, retrieval policies, fixtures, schema fields or graders changes an experiment.
Version the protocol, publish the exact new settings and rerun affected comparisons. Do not tune
against reported evaluation outcomes and continue presenting them as held-out results.

Publish only reviewed synthetic traces. Keep private data, local databases, credentials, model
weights and workstation-specific paths out of commits. Negative results and infrastructure
failures belong in reports. Small samples require modest claims.
