# Sales pipeline agent (MCP + Claude)

A Claude agent that answers "What's our pipeline this quarter by stage?" by calling tools on an MCP server
backed by `data/opportunities.csv` (60 sample opportunities, close dates Jul 2026 – Mar 2027).

| File | Role |
|---|---|
| `pipeline.py` | Pure logic: quarter parsing, stage aggregation (no MCP dependency) |
| `server.py` | MCP server (stdio): `get_current_quarter`, `pipeline_by_stage`, `list_opportunities` |
| `agent.py` | Claude tool-use loop over the MCP server (`claude-sonnet-5-5`, override with `AGENT_MODEL`) |
| `evals/` | 10 cases (`cases.json`), independent ground truth (`truth.py`), graders, live runner |
| `tests/` | Offline tests: logic, graders, and agent loop with a fake Claude client |

## Architecture
```
 question ─► agent.py (Claude tool-use loop) ──stdio/MCP──► server.py ─► pipeline.py ─► data/opportunities.csv
                 ▲                                              │
                 └────────── tool results (JSON) ◄──────────────┘
 evals/: cases.json ─► agent ─► graders.py, checked against truth.py (reads the CSV directly, not pipeline.py)
```
Claude decides which tool to call; the server does all date and sum logic, so numbers come from code, not the model.

Definitions: *pipeline* = open stages (Prospecting, Qualification, Proposal, Negotiation) with expected close date
in the calendar quarter. Closed Won / Closed Lost are excluded (closed-won is reported separately).
Weighted pipeline uses 10/25/50/75%.

## Run
```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt   # mcp needs Python >= 3.10
export ANTHROPIC_API_KEY=...
.venv/bin/python agent.py "What's our pipeline this quarter by stage?"
.venv/bin/python -m pytest -q tests                      # offline, no key needed
.venv/bin/python -m evals.run_evals --trials 3           # live evals; "today" pinned to 2026-10-05
```
To use the server from another MCP client: `command: .venv/bin/python, args: [server.py]`.

## Eval design
Expected numbers come from `evals/truth.py`, which reads the CSV directly, so a bug in `pipeline.py` can't
make a wrong answer look right. Cases cover: the headline question, next/explicit quarters, totals, weighted,
closed-won vs pipeline, top stage, owner filter, a quarter with no data (must not invent figures), and an
unsupported dimension (region; must say it's unavailable). The data includes quarter-boundary dates
(2026-09-30, 10-01, 12-31, 2027-01-01) and a large Closed Lost deal, and the graders fail any answer that
lumps closed deals into the pipeline total. Graders accept `$1.2M`/`$450K`/`1,234,567` within display rounding.
