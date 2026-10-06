"""Claude agent that answers sales-pipeline questions via the MCP server in server.py.

Usage: ANTHROPIC_API_KEY=... python agent.py "What's our pipeline this quarter by stage?"
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5-5")
HERE = Path(__file__).parent
SYSTEM = """You are a sales-operations analyst. Answer questions about the sales pipeline using ONLY the tools provided.
- Resolve relative dates like "this quarter" with get_current_quarter; never assume today's date.
- "Pipeline" means open opportunities (Prospecting, Qualification, Proposal, Negotiation). Closed Won and Closed Lost are not pipeline.
- Report figures exactly as the tools return them (you may format as $1.2M). Never estimate or invent numbers.
- If the data cannot answer the question (missing field, no data for the period), say so plainly instead of guessing.
- Use as few tool calls as possible (usually one or two). Never retry with different filters to hunt for a field the data does not have; if a filter matches nothing, or the data lacks the field, say so and stop.
- Be concise: lead with the answer, show a small stage table when asked for a breakdown, state the quarter used."""


@asynccontextmanager
async def mcp_session():
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "server.py")], env=dict(os.environ))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            yield session


async def ask(question: str, session: ClientSession, max_turns: int = 6) -> dict:
    """Run the tool-use loop. Returns {"answer": str, "tool_calls": [{"name", "input", "result"}]}."""
    client = anthropic.AsyncAnthropic(timeout=60.0, max_retries=2)
    tools = [{"name": t.name, "description": t.description, "input_schema": t.inputSchema}
             for t in (await session.list_tools()).tools]
    messages = [{"role": "user", "content": question}]
    calls = []
    for _ in range(max_turns):
        resp = await client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM,
                                            tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {"answer": text, "tool_calls": calls}
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                out = await session.call_tool(b.name, b.input)
                text = "".join(c.text for c in out.content if c.type == "text")
                print(f"    [tool] {b.name}({dict(b.input)})", file=sys.stderr, flush=True)
                calls.append({"name": b.name, "input": b.input, "result": text})
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": text,
                                "is_error": bool(out.isError)})
        messages.append({"role": "user", "content": results})
    return {"answer": "(max turns reached)", "tool_calls": calls}


async def main(question: str):
    async with mcp_session() as session:
        result = await ask(question, session)
    for c in result["tool_calls"]:
        print(f"[tool] {c['name']}({c['input']})", file=sys.stderr)
    print(result["answer"])


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "What's our pipeline this quarter by stage?"))
