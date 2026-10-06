"""Run the eval set against the live agent.  Usage:
    ANTHROPIC_API_KEY=... python -m evals.run_evals [--trials 3] [--only id1,id2]
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PIPELINE_AS_OF", "2026-10-05")  # pin "today" so expectations are stable

from agent import ask, mcp_session  # noqa: E402
from .graders import grade  # noqa: E402

HERE = Path(__file__).parent


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    cases = json.loads((HERE / "cases.json").read_text())
    if args.only:
        cases = [c for c in cases if c["id"] in args.only.split(",")]

    results, passed = [], 0
    async with mcp_session() as session:
        for case in cases:
            for t in range(args.trials):
                print(f"RUN   {case['id']} (trial {t + 1}) ...", flush=True)
                try:
                    out = await asyncio.wait_for(ask(case["question"], session), timeout=120)
                except asyncio.TimeoutError:
                    out = {"answer": "(timed out after 120s)", "tool_calls": []}
                fails = grade(case, out["answer"], out["tool_calls"])
                passed += not fails
                print(f"{'PASS' if not fails else 'FAIL'}  {case['id']} (trial {t + 1})")
                for f in fails:
                    print(f"      - {f}")
                results.append({"id": case["id"], "trial": t + 1, "failures": fails, **out})
    total = len(results)
    print(f"\n{passed}/{total} passed")
    (HERE / "results.json").write_text(json.dumps(results, indent=2, default=str))
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
