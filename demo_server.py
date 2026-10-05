"""Talk to the MCP server directly (no Claude / API key): list its tools and call them."""
import asyncio
import json
import os

os.environ.setdefault("PIPELINE_AS_OF", "2026-10-05")
from agent import mcp_session


async def main():
    async with mcp_session() as s:
        print("TOOLS:", [t.name for t in (await s.list_tools()).tools], "\n")
        for name, args in [("get_current_quarter", {}),
                           ("pipeline_by_stage", {}),
                           ("list_opportunities", {"stage": "Negotiation", "limit": 3})]:
            r = await s.call_tool(name, args)
            print(f"> {name}({args})\n{json.dumps(json.loads(r.content[0].text), indent=2)}\n")

asyncio.run(main())
