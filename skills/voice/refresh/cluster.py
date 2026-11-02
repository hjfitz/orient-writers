#!/usr/bin/env python3
"""Split human.json (written by analyse.py) into audience clusters. Edit the name sets for the current team."""
import json, collections
h = json.load(open("human.json"))
reports = {"Matt Shaw", "Nylah Klasson", "Harry Humby", "Schuster Efigenio"}
seniors = {"Oli Denton", "john.clarke"}
def people(ch):
    if ch.startswith("DM:"): return {ch[3:]}
    if ch.startswith("GDM:"): return set(ch[4:].split("+"))
    return set()
def cluster(r):
    if r["kind"] in ("public", "private"): return "channels"
    p = people(r["ch"])
    if "Jack Bailey" in p: return "jack"
    if r["ch"] == "DM:Darren Rielly": return "darren"
    if p & seniors and not (p & reports): return "oli"
    if p & reports: return "reports"
    return "wider"
cl = collections.defaultdict(list)
for r in h: cl[cluster(r)].append(r)
for k, v in cl.items():
    with open(f"cluster-{k}.jsonl", "w") as f:
        for r in sorted(v, key=lambda r: (r["date"], r["time"])): f.write(json.dumps(r) + "\n")
    print(k, len(v))
