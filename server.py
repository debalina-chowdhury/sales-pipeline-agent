"""MCP server exposing the sales-opportunities CSV. Run over stdio: `python server.py`."""
from mcp.server.fastmcp import FastMCP

import pipeline

mcp = FastMCP("sales-pipeline")


@mcp.tool()
def get_current_quarter() -> dict:
    """Return today's date and the current calendar quarter (label like '2026-Q4' with start/end dates).
    Call this to resolve 'this quarter' before querying."""
    return pipeline.current_quarter()


@mcp.tool()
def pipeline_by_stage(quarter: str | None = None, owner: str | None = None) -> dict:
    """Open sales pipeline grouped by stage (Prospecting, Qualification, Proposal, Negotiation) for a
    calendar quarter, based on expected close date. Returns count, amount and probability-weighted amount
    per stage, totals, and closed-won for the quarter. Closed Won/Lost are NOT pipeline.

    Args:
        quarter: e.g. '2026-Q4'. Omit for the current quarter.
        owner: optional exact opportunity-owner name to filter by.
    """
    return pipeline.pipeline_by_stage(quarter, owner)


@mcp.tool()
def list_opportunities(quarter: str | None = None, stage: str | None = None,
                       owner: str | None = None, limit: int = 25) -> dict:
    """List individual opportunities (largest first) closing in a calendar quarter, for drill-down.
    Includes closed stages. Columns: opportunity_id, account, owner, stage, amount, close_date.

    Args:
        quarter: e.g. '2026-Q4'. Omit for the current quarter.
        stage: optional stage name filter (any of the six stages, including Closed Won/Closed Lost).
        owner: optional opportunity-owner filter.
        limit: max rows to return (default 25).
    """
    return pipeline.list_opportunities(quarter, stage, owner, limit)


if __name__ == "__main__":
    mcp.run()
