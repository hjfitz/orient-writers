import os, json, re, glob, os

D = (os.environ.get("VOICE_WORK") or os.getcwd()).rstrip("/") + "/"
V = os.path.expanduser("~/Documents/obsidian/Voice/")

rows = []
for f in glob.glob(D + "corpus-*.jsonl"):
    for l in open(f):
        rows.append(json.loads(l))

def norm(s):
    s = s.replace("\\n", " ").replace("\n", " ")
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().lower()

blob_human = norm(" || ".join(r["text"] for r in rows if not r["agent_suspect"]))
blob_suspect = norm(" || ".join(r["text"] for r in rows if r["agent_suspect"]))

tot = ok = 0
for f in sorted(glob.glob(V + "*.md") + glob.glob(V + "Registers/*.md")):
    md = open(f).read()
    body = md.split("---", 2)[-1]
    qs = set(m.group(1) for m in re.finditer(r'"([^"\n]{5,600})"', body))
    bad = []
    for q in sorted(qs):
        parts = [p for p in re.split(r"\s*(?:\.\.\.|…|<name>)\s*", q) if len(p) >= 5]
        if not parts:
            continue
        tot += 1
        if all(norm(p) in blob_human for p in parts):
            ok += 1
        elif all(norm(p) in blob_suspect for p in parts):
            bad.append(("IN-AGENT-ROWS", q))
        else:
            bad.append(("NOT-IN-CORPUS", q))
    print(f"{os.path.relpath(f, V)}: quoted={len(qs)} unmatched={len(bad)}")
    for kind, q in bad:
        print(f"    [{kind}] {q[:150]}")
print(f"\nTOTAL checked={tot} exact-in-human-corpus={ok}")
