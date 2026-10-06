"""Pure pipeline logic over the opportunities CSV (no MCP dependency, easy to unit test)."""
import csv
import difflib
import os
import re
from datetime import date
from pathlib import Path

DATA_PATH = Path(os.environ.get("OPPORTUNITIES_CSV", Path(__file__).parent / "data" / "opportunities.csv"))

OPEN_STAGES = ["Prospecting", "Qualification", "Proposal", "Negotiation"]
CLOSED_STAGES = ["Closed Won", "Closed Lost"]
# Stage-based win probability used for weighted pipeline.
STAGE_PROBABILITY = {"Prospecting": 0.10, "Qualification": 0.25, "Proposal": 0.50, "Negotiation": 0.75}


def today() -> date:
    """Current date; PIPELINE_AS_OF=YYYY-MM-DD pins it so evals are reproducible."""
    return date.fromisoformat(os.environ["PIPELINE_AS_OF"]) if os.environ.get("PIPELINE_AS_OF") else date.today()


def load() -> list[dict]:
    with DATA_PATH.open(newline="") as f:
        return [
            {**r, "amount": int(r["amount"]), "close_date": date.fromisoformat(r["close_date"])}
            for r in csv.DictReader(f)
        ]


def quarter_bounds(year: int, q: int) -> tuple[date, date]:
    start = date(year, 3 * q - 2, 1)
    end = date(year + (q == 4), 1 if q == 4 else 3 * q + 1, 1)
    return start, date.fromordinal(end.toordinal() - 1)


def parse_quarter(text: str | None) -> tuple[int, int]:
    """Calendar quarter from '2026-Q4' / 'Q4 2026' / None (= current quarter)."""
    if not text:
        d = today()
        return d.year, (d.month - 1) // 3 + 1
    t = text.strip().upper()
    m = re.fullmatch(r"(\d{4})[-\s]?Q([1-4])", t) or None
    if m:
        return int(m[1]), int(m[2])
    m = re.fullmatch(r"Q([1-4])[-\s]?(\d{4})", t)
    if m:
        return int(m[2]), int(m[1])
    raise ValueError(f"Unrecognised quarter {text!r}; use e.g. '2026-Q4'.")


def current_quarter() -> dict:
    y, q = parse_quarter(None)
    s, e = quarter_bounds(y, q)
    return {"quarter": f"{y}-Q{q}", "start": s.isoformat(), "end": e.isoformat(), "as_of": today().isoformat()}


def _unknown_owner(owner: str | None) -> dict | None:
    """Error payload (with closest-match suggestions) if `owner` matches nobody in the data."""
    owners = sorted({r["owner"] for r in load()})
    if not owner or owner.lower() in {o.lower() for o in owners}:
        return None
    return {"error": f"No opportunity owner named {owner!r}.",
            "did_you_mean": difflib.get_close_matches(owner, owners, n=2, cutoff=0.6),
            "valid_owners": owners,
            "instruction": "Do not report $0. Tell the user the name was not found and confirm the suggested match."}


def _in_quarter(rows: list[dict], quarter: str | None) -> tuple[str, list[dict]]:
    y, q = parse_quarter(quarter)
    s, e = quarter_bounds(y, q)
    return f"{y}-Q{q}", [r for r in rows if s <= r["close_date"] <= e]


def pipeline_by_stage(quarter: str | None = None, owner: str | None = None) -> dict:
    """Open pipeline (by expected close date in the quarter) grouped by stage.

    Closed Won / Closed Lost are not pipeline; Closed Won is reported separately as `closed_won`.
    """
    if err := _unknown_owner(owner):
        return err
    label, rows = _in_quarter(load(), quarter)
    if owner:
        rows = [r for r in rows if r["owner"].lower() == owner.lower()]
    stages = []
    for st in OPEN_STAGES:
        sr = [r for r in rows if r["stage"] == st]
        amt = sum(r["amount"] for r in sr)
        stages.append({"stage": st, "count": len(sr), "amount": amt,
                       "weighted_amount": round(amt * STAGE_PROBABILITY[st])})
    won = [r for r in rows if r["stage"] == "Closed Won"]
    return {
        "quarter": label,
        "owner": owner,
        "stages": stages,
        "total_open_pipeline": sum(s["amount"] for s in stages),
        "total_weighted_pipeline": sum(s["weighted_amount"] for s in stages),
        "open_deal_count": sum(s["count"] for s in stages),
        "closed_won": {"count": len(won), "amount": sum(r["amount"] for r in won)},
        "notes": "Pipeline excludes Closed Won and Closed Lost. Weighted uses stage probabilities: "
                 + ", ".join(f"{k} {int(v*100)}%" for k, v in STAGE_PROBABILITY.items()) + ".",
    }


def list_opportunities(quarter: str | None = None, stage: str | None = None,
                       owner: str | None = None, limit: int = 25) -> dict:
    if err := _unknown_owner(owner):
        return err
    label, rows = _in_quarter(load(), quarter)
    if stage:
        rows = [r for r in rows if r["stage"].lower() == stage.lower()]
    if owner:
        rows = [r for r in rows if r["owner"].lower() == owner.lower()]
    rows.sort(key=lambda r: -r["amount"])
    out = {
        "quarter": label,
        "total_matches": len(rows),
        "opportunities": [{**r, "close_date": r["close_date"].isoformat()} for r in rows[:limit]],
    }
    if not rows:
        out["hint"] = ("No matches. Valid stages: " + ", ".join(OPEN_STAGES + CLOSED_STAGES)
                       + ". Valid owners: " + ", ".join(sorted({r["owner"] for r in load()}))
                       + ". The data has no other fields (e.g. no region); do not retry with other filters.")
    return out
