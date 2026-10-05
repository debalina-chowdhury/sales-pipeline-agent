"""Ground truth computed straight from the CSV, deliberately independent of pipeline.py."""
import csv
from datetime import date
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "data" / "opportunities.csv"
OPEN = ["Prospecting", "Qualification", "Proposal", "Negotiation"]
PROB = {"Prospecting": .10, "Qualification": .25, "Proposal": .50, "Negotiation": .75}


def rows_for(quarter: str, owner: str | None = None):
    year, q = int(quarter[:4]), int(quarter[-1])
    lo, hi = (year, 3 * q - 2), (year, 3 * q)
    out = []
    for r in csv.DictReader(CSV.open()):
        d = date.fromisoformat(r["close_date"])
        if (d.year, d.month) < lo or (d.year, d.month) > hi:
            continue
        if owner and r["owner"] != owner:
            continue
        out.append({**r, "amount": int(r["amount"])})
    return out


def by_stage(quarter, owner=None):
    rows = rows_for(quarter, owner)
    return {s: sum(r["amount"] for r in rows if r["stage"] == s) for s in OPEN}


def metric(quarter, name, owner=None):
    rows = rows_for(quarter, owner)
    bs = by_stage(quarter, owner)
    if name == "total_open":
        return sum(bs.values())
    if name == "total_weighted":
        return sum(v * PROB[s] for s, v in bs.items())
    if name == "closed_won":
        return sum(r["amount"] for r in rows if r["stage"] == "Closed Won")
    if name == "total_all_stages":  # the wrong answer: open + closed lumped together
        return sum(r["amount"] for r in rows)
    raise KeyError(name)
