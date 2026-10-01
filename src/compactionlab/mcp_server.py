"""MCP adapter to the same database used by the HTTP service."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from compactionlab.schemas import ContextRequest, WriteBatch
from compactionlab.store import Store


def create_server(data_dir: Path):
    store = Store(data_dir / "memory.sqlite3")
    server = FastMCP("CompactionLab")

    @server.tool()
    def memory_namespaces() -> list[dict]:
        """List available task scopes. These are local scopes, not access-control boundaries."""
        return store.namespaces()

    @server.tool()
    def memory_snapshot(namespace: str) -> dict:
        """Inspect records and their original sources, including historical/superseded records."""
        return store.snapshot(namespace)

    @server.tool()
    def memory_append(namespace: str, batch: dict) -> dict:
        """Append sourced records atomically with expected_revision. Old records are immutable."""
        revision = store.write(namespace, WriteBatch.model_validate(batch))
        return {"revision": revision}

    @server.tool()
    def context_query(namespace: str, query: str, byte_budget: int = 6000) -> dict:
        """Retrieve a bounded, sourced context bundle. Returned facts may still be incorrect."""
        return store.context(namespace, ContextRequest(query=query, byte_budget=byte_budget))

    return server
