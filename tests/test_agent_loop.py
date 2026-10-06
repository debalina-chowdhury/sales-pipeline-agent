"""Exercise agent.ask() against the real MCP server with a scripted fake Anthropic client (no API key)."""
import asyncio
import os
from types import SimpleNamespace as NS

os.environ["PIPELINE_AS_OF"] = "2026-10-05"

import agent
from evals import truth
from evals.graders import grade


def test_agent_loop_calls_tool_and_returns_text(monkeypatch):
    seen = []

    class FakeMessages:
        async def create(self, **kw):
            seen.append(kw["messages"][-1])
            if len(seen) == 1:
                assert {t["name"] for t in kw["tools"]} == {"get_current_quarter", "pipeline_by_stage", "list_opportunities"}
                call = NS(type="tool_use", id="t1", name="pipeline_by_stage", input={})
                return NS(stop_reason="tool_use", content=[call])
            result = seen[-1]["content"][0]
            assert result["tool_use_id"] == "t1" and not result["is_error"]
            total = truth.metric("2026-Q4", "total_open")
            return NS(stop_reason="end_turn", content=[NS(type="text", text=f"Open pipeline: ${total:,}")])

    monkeypatch.setattr(agent.anthropic, "AsyncAnthropic", lambda **kw: NS(messages=FakeMessages()))

    async def run():
        async with agent.mcp_session() as s:
            return await agent.ask("pipeline?", s)

    out = asyncio.run(run())
    assert out["tool_calls"][0]["name"] == "pipeline_by_stage"
    case = {"expect": {"kind": "numbers", "quarter": "2026-Q4", "metric": "total_open", "must_call": ["pipeline_by_stage"]}}
    assert grade(case, out["answer"], out["tool_calls"]) == []
