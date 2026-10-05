"""Generate data/opportunities.csv deterministically (seeded) plus hand-placed edge cases."""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(7)
OUT = Path(__file__).resolve().parent.parent / "data" / "opportunities.csv"

ACCOUNTS = ["Acme Corp", "Globex", "Initech", "Umbrella", "Hooli", "Stark Industries", "Wayne Enterprises",
            "Wonka", "Soylent", "Cyberdyne", "Tyrell", "Vandelay", "Pied Piper", "Massive Dynamic",
            "Oscorp", "Aperture", "Black Mesa", "Dunder Mifflin", "Gringotts", "Monarch"]
OWNERS = ["Alice Nguyen", "Bob Martinez", "Carla Singh", "Dev Patel"]
STAGES = ["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]

rows = []

# Hand-placed edge cases: quarter boundaries, closed deals inside the quarter, same-account duplicates.
edge = [
    ("Acme Corp",        "Alice Nguyen", "Negotiation",   250000, "2026-10-01"),  # first day of Q4
    ("Globex",           "Bob Martinez", "Proposal",      120000, "2026-12-31"),  # last day of Q4
    ("Initech",          "Carla Singh",  "Qualification",  80000, "2027-01-01"),  # first day of Q1 2027
    ("Umbrella",         "Dev Patel",    "Prospecting",    60000, "2026-09-30"),  # last day of Q3
    ("Hooli",            "Alice Nguyen", "Closed Won",    300000, "2026-10-02"),  # closed, in Q4: not pipeline
    ("Stark Industries", "Bob Martinez", "Closed Lost",   500000, "2026-11-15"),  # lost, in Q4: not pipeline
]
for acct, owner, stage, amt, close in edge:
    rows.append((acct, owner, stage, amt, close))

# Random bulk: close dates between 2026-07-01 and 2027-03-31.
start, end = date(2026, 7, 1), date(2027, 3, 31)
span = (end - start).days
for _ in range(54):
    stage = random.choices(STAGES, weights=[18, 16, 14, 10, 8, 6])[0]
    amt = random.randrange(15, 400) * 1000
    close = start + timedelta(days=random.randrange(span + 1))
    rows.append((random.choice(ACCOUNTS), random.choice(OWNERS), stage, amt, close.isoformat()))

rows.sort(key=lambda r: r[4])
OUT.parent.mkdir(exist_ok=True)
with OUT.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["opportunity_id", "account", "owner", "stage", "amount", "close_date"])
    for i, r in enumerate(rows, 1):
        w.writerow([f"OPP-{i:04d}", *r])
print(f"wrote {len(rows)} rows to {OUT}")
