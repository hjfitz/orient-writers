#!/usr/bin/env python3
"""Seeded random-weekday sample for a voice re-mine. Edit PLAN, run, then give each agent its slice of manifest.json.
Weights recent months more heavily. Prints the days per agent (round-robin so a failed agent costs little bias)."""
import random, datetime as dt, json, sys
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 20260930
n_agents = int(sys.argv[2]) if len(sys.argv) > 2 else 6
random.seed(seed)
# (year, month, days_to_sample, first_day, last_day or None) -- extend/replace for the window you are mining
PLAN = [(2026, 4, 5, 1, None), (2026, 5, 5, 1, None), (2026, 6, 5, 1, None), (2026, 7, 5, 1, None),
        (2026, 8, 5, 1, None), (2026, 9, 5, 1, 28)]
def weekdays(y, m, lo=1, hi=None):
    d = dt.date(y, m, lo); out = []
    while d.month == m and (hi is None or d.day <= hi):
        if d.weekday() < 5: out.append(d)
        d += dt.timedelta(days=1)
    return out
days = []
for y, m, n, lo, hi in PLAN:
    days += random.sample(weekdays(y, m, lo, hi), n)
days.sort()
agents = [[] for _ in range(n_agents)]
for i, d in enumerate(days): agents[i % n_agents].append(d.isoformat())
json.dump(agents, open("manifest.json", "w"), indent=1)
for i, a in enumerate(agents, 1): print(i, a)
