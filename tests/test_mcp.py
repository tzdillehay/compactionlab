import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from compactionlab.packets import expand_packet


def test_real_mcp_stdio_round_trip(tmp_path):
    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "compactionlab.cli", "--data-dir", str(tmp_path), "mcp"],
            env=dict(os.environ),
        )
        async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "memory_namespaces",
                "memory_snapshot",
                "memory_append",
                "context_query",
            }
            result = await session.call_tool(
                "memory_append",
                {
                    "namespace": "handoff",
                    "batch": {
                        "expected_revision": 0,
                        "events": [
                            {"id": "e", "source": "user", "text": "Current deadline is Tuesday"}
                        ],
                        "records": [
                            {
                                "id": "r",
                                "kind": "requirement",
                                "text": "Deadline is Tuesday",
                                "source_ids": ["e"],
                            }
                        ],
                    },
                },
            )
            assert not result.isError
            context = await session.call_tool(
                "context_query", {"namespace": "handoff", "query": "deadline"}
            )
            assert not context.isError
            assert "Tuesday" in context.content[0].text
            compact = await session.call_tool(
                "context_query", {"namespace": "handoff", "query": "deadline", "mode": "compact"}
            )
            assert not compact.isError
            verbose_data = json.loads(context.content[0].text)
            compact_data = json.loads(compact.content[0].text)
            assert expand_packet(compact_data["text"]) == json.loads(verbose_data["text"])
            assert (tmp_path / "memory.sqlite3").is_file()

    asyncio.run(exercise())
