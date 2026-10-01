# References and attribution

- [MemGPT](https://arxiv.org/abs/2310.08560): external memory and management of a limited working context.
- [Letta memory blocks](https://www.letta.com/blog/memory-blocks/): persisted shared context blocks.
- [Mem0](https://github.com/mem0ai/mem0): external memory extraction and retrieval.
- [Graphiti](https://github.com/getzep/graphiti): temporal knowledge graphs for evolving agent context.
- [Zep facts](https://help.getzep.com/facts): provenance and validity intervals; validity is not proof of truth.
- [MCP](https://modelcontextprotocol.io/introduction): interoperability for tools and external context.
- [Qwen3 4B](https://huggingface.co/Qwen/Qwen3-4B) and
  [Qwen3 8B](https://huggingface.co/Qwen/Qwen3-8B): upstream model cards and licenses.
- [Ollama](https://github.com/ollama/ollama): local model runtime.
- [TypeSafe / Jev](https://docs.typesafe.ai/cookbooks/rerank_typesafe): possible future decision-model reranking adapter.
- [TRACE](https://arxiv.org/abs/2608.06503): related paired-continuation compaction evaluation.
- [LongMemEval](https://github.com/xiaowu0162/LongMemEval): knowledge updates, temporal reasoning,
  multi-session recall and abstention, with oracle-source controls.
- [LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2): agent-trajectory memory,
  dynamic state, workflow knowledge, and accuracy/query-latency evaluation. A candidate external
  validation harness; CompactionLab has not run it or reproduced its results.

CompactionLab original code and synthetic fixtures use Apache-2.0. No source code or weights from
these projects are copied into the original implementation. Installed dependencies have their
own licenses, which are preserved by their distributions. Model weights are downloaded separately
and never committed. Citation of a project does not imply endorsement or benchmark equivalence.
