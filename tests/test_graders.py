"""Sanity-check the eval graders themselves with canned good and bad answers (no API calls)."""
import json

from evals import truth
from evals.graders import grade, has_amount, numbers

Q = "2026-Q4"
BS = truth.by_stage(Q)
TRACE = [{"name": "pipeline_by_stage", "input": {"quarter": Q},
          "result": json.dumps({"quarter": Q})}]
CASE = {"expect": {"kind": "stage_breakdown", "quarter": Q, "must_call": ["pipeline_by_stage"]}}


def good_answer():
    lines = [f"{s}: ${v:,}" for s, v in BS.items()]
    return "\n".join(lines) + f"\nTotal: ${sum(BS.values()):,}"


def test_number_parsing_and_tolerance():
    assert numbers("$1.2M and 450k and $2,500,000 and 3 million") == [
        (1.2e6, 5e4), (450e3, 500), (2.5e6, 0.5), (3e6, 5e5)]
    assert has_amount("about $1.2M", 1_234_567) and not has_amount("about $1.2M", 1_400_000)


def test_good_answer_passes_even_when_abbreviated():
    assert grade(CASE, good_answer(), TRACE) == []
    short = "\n".join(f"{s}: ${v/1000:.0f}K" for s, v in BS.items()) + f"\nTotal ${sum(BS.values())/1e6:.2f}M"
    assert grade(CASE, short, TRACE) == []


def test_wrong_number_and_missing_tool_fail():
    bad = good_answer().replace(f"{max(BS.values()):,}", "1")
    assert grade(CASE, bad, TRACE)
    assert any("did not call" in f for f in grade(CASE, good_answer(), []))


def test_including_closed_deals_is_caught():
    wrong = truth.metric(Q, "total_all_stages")
    fails = grade(CASE, good_answer() + f"\nTotal incl. everything: ${wrong:,}", TRACE)
    assert any("closed deals" in f for f in fails)


def test_no_data_and_unsupported():
    nd = {"expect": {"kind": "no_data", "quarter": "2030-Q2"}}
    assert grade(nd, "There are no opportunities closing in Q2 2030.", []) == []
    assert grade(nd, "Q2 2030 pipeline is $1.5M.", [])
    un = {"expect": {"kind": "unsupported", "forbidden_regions": ["EMEA", "APAC"]}}
    assert grade(un, "The data has no region field, so I can't break it down by region.", []) == []
    assert grade(un, "EMEA has $1M and APAC $2M by region.", [])


def test_hard_case_graders():
    ty = {"expect": {"kind": "owner_typo", "quarter": Q, "owner": "Alice Nguyen"}}
    total = truth.metric(Q, "total_open", owner="Alice Nguyen")
    assert grade(ty, f"Assuming you mean Alice Nguyen: ${total:,}.", []) == []
    assert grade(ty, "I couldn't find an owner named Ngyuen. Did you mean Alice Nguyen?", []) == []
    assert grade(ty, "Alice Ngyuen has $0 in open pipeline.", [])

    mu = {"expect": {"kind": "multi", "quarter": Q, "metrics": ["total_open", "closed_won"], "forbid": "total_all_stages"}}
    o, w = truth.metric(Q, "total_open"), truth.metric(Q, "closed_won")
    assert grade(mu, f"Open: ${o:,}. Closed-won: ${w:,}. Combined ${o + w:,}.", []) == []
    assert grade(mu, f"Total ${truth.metric(Q, 'total_all_stages'):,}; open ${o:,}; won ${w:,}", [])

    dd = {"expect": {"kind": "date_deals", "date": "2026-12-31", "neighbour": "2027-01-01"}}
    assert grade(dd, "OPP-0042 (Globex) for $120,000 closes that day.", []) == []
    assert any("OPP-0043" in f for f in grade(dd, "OPP-0042 and OPP-0043, $120,000", []))
