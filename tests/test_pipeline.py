import os

os.environ["PIPELINE_AS_OF"] = "2026-10-05"

import pytest

import pipeline
from evals import truth


def test_current_quarter():
    assert pipeline.current_quarter() == {
        "quarter": "2026-Q4", "start": "2026-10-01", "end": "2026-12-31", "as_of": "2026-10-05"}


@pytest.mark.parametrize("text,expected", [("2026-Q4", (2026, 4)), ("q1 2027", (2027, 1)), ("2026Q3", (2026, 3))])
def test_parse_quarter(text, expected):
    assert pipeline.parse_quarter(text) == expected


def test_parse_quarter_rejects_garbage():
    with pytest.raises(ValueError):
        pipeline.parse_quarter("next quarter")


def test_stage_amounts_match_independent_truth():
    for quarter in ["2026-Q3", "2026-Q4", "2027-Q1"]:
        got = {s["stage"]: s["amount"] for s in pipeline.pipeline_by_stage(quarter)["stages"]}
        assert got == truth.by_stage(quarter)


def test_pipeline_excludes_closed_deals_and_includes_boundary_days():
    r = pipeline.pipeline_by_stage("2026-Q4")
    stages = {s["stage"]: s for s in r["stages"]}
    assert "Closed Lost" not in stages and "Closed Won" not in stages
    assert r["total_open_pipeline"] == sum(s["amount"] for s in r["stages"])
    ids = {o["opportunity_id"] for o in pipeline.list_opportunities("2026-Q4", limit=100)["opportunities"]}
    dates = {o["close_date"] for o in pipeline.list_opportunities("2026-Q4", limit=100)["opportunities"]}
    assert "2026-10-01" in dates and "2026-12-31" in dates          # both ends inclusive
    assert "2026-09-30" not in dates and "2027-01-01" not in dates  # neighbours excluded
    assert r["closed_won"]["amount"] == truth.metric("2026-Q4", "closed_won")


def test_weighted_and_owner_filter():
    r = pipeline.pipeline_by_stage("2026-Q4")
    assert r["total_weighted_pipeline"] == pytest.approx(truth.metric("2026-Q4", "total_weighted"), abs=2)
    a = pipeline.pipeline_by_stage("2026-Q4", owner="alice nguyen")
    assert a["total_open_pipeline"] == truth.metric("2026-Q4", "total_open", owner="Alice Nguyen")


def test_empty_quarter():
    r = pipeline.pipeline_by_stage("2030-Q2")
    assert r["total_open_pipeline"] == 0 and r["open_deal_count"] == 0


def test_unknown_owner_is_an_error_not_zero():
    for fn in (pipeline.pipeline_by_stage, pipeline.list_opportunities):
        r = fn("2026-Q4", owner="Alice Ngyuen")
        assert "error" in r and "total_open_pipeline" not in r
        assert r["did_you_mean"][0] == "Alice Nguyen"
