"""Deterministic graders. Each returns a list of failure strings (empty list = pass)."""
import json
import re

from . import truth

_NUM = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(million|billion|thousand|[mbk])?\b", re.I)
_MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


def numbers(text: str) -> list[tuple[float, float]]:
    """All numbers in text as (value, tolerance). Tolerance is half a unit of the last displayed digit,
    so '$1.2M' matches 1,150,000-1,250,000 and '$1,234,567' must be near-exact."""
    out = []
    for m in _NUM.finditer(text):
        raw, suf = m.group(1).replace(",", ""), (m.group(2) or "").lower()
        mult = _MULT.get(suf, 1)
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        out.append((float(raw) * mult, 0.5 * mult * 10 ** -decimals))
    return out


def has_amount(text: str, expected: float) -> bool:
    return any(abs(v - expected) <= max(t, 0.002 * expected) for v, t in numbers(text))


def _tool_results(trace, name):
    for c in trace:
        if c["name"] == name:
            try:
                yield c, json.loads(c["result"])
            except ValueError:
                pass


def grade(case: dict, answer: str, trace: list[dict]) -> list[str]:
    e, fails = case["expect"], []
    kind, q, owner = e["kind"], e.get("quarter"), e.get("owner")
    called = {c["name"] for c in trace}

    for tool in e.get("must_call", []):
        if tool not in called:
            fails.append(f"did not call {tool}")
    if "pipeline_by_stage" in e.get("must_call", []):
        if not any(r.get("quarter") == q for _, r in _tool_results(trace, "pipeline_by_stage")):
            fails.append(f"pipeline_by_stage never queried {q}")
        if owner and not any(c["input"].get("owner") == owner for c, _ in _tool_results(trace, "pipeline_by_stage")):
            fails.append(f"owner filter {owner!r} not passed to the tool")

    if kind == "stage_breakdown":
        bs = truth.by_stage(q, owner)
        for stage, amt in bs.items():
            if amt and not has_amount(answer, amt):
                fails.append(f"{stage} amount {amt:,} missing")
        if not has_amount(answer, sum(bs.values())):
            fails.append(f"total open pipeline {sum(bs.values()):,} missing")
        wrong = truth.metric(q, "total_all_stages", owner)
        if wrong != sum(bs.values()) and has_amount(answer, wrong):
            fails.append(f"reports {wrong:,}, which wrongly includes closed deals")
    elif kind == "numbers":
        want = truth.metric(q, e["metric"], owner)
        if not has_amount(answer, want):
            fails.append(f"{e['metric']} {want:,.0f} missing")
        if e["metric"] == "total_open":
            wrong = truth.metric(q, "total_all_stages", owner)
            if has_amount(answer, wrong):
                fails.append(f"reports {wrong:,}, which wrongly includes closed deals")
    elif kind == "top_stage":
        bs = truth.by_stage(q)
        top = max(bs, key=bs.get)
        pos = {s: answer.lower().find(s.lower()) for s in bs if s.lower() in answer.lower()}
        if not pos or min(pos, key=pos.get) != top:
            fails.append(f"expected {top} as the top stage, got order {sorted(pos, key=pos.get)}")
    elif kind == "no_data":
        if any(v >= 1 for v, _ in numbers(re.sub(r"\b20\d\d\b|\bQ\d\b", "", answer))):
            fails.append("states non-zero figures for a quarter with no data")
        if not re.search(r"\bno\b|none|\$0\b|zero|\b0\b|not (?:any|have)|nothing", answer, re.I):
            fails.append("does not say there is no data")
    elif kind == "unsupported":
        for region in e["forbidden_regions"]:
            if re.search(rf"\b{re.escape(region)}\b", answer):
                fails.append(f"invented region {region!r}")
        if not re.search(r"region", answer, re.I) or not re.search(
                r"no |not |n't|cannot|can't|unavailable|lack|doesn't|does not|without", answer, re.I):
            fails.append("does not explain that region data is unavailable")
    return fails
