import os, json, re, sys, glob

D = (os.environ.get("VOICE_WORK") or os.getcwd()).rstrip("/") + "/"
name = sys.argv[1]
md = open(D + f"profile-{name}.md").read()

corpus = []
for f in glob.glob(D + "cluster-*.jsonl"):
    for l in open(f):
        corpus.append(json.loads(l))
own = [r["text"] for r in corpus if True]
cl = [json.loads(l)["text"] for l in open(D + f"cluster-{name}.jsonl")]

def norm(s):
    s = s.replace("\\n", " ").replace("\n", " ")
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().lower()

blob_cluster = norm(" || ".join(cl))
blob_all = norm(" || ".join(own))

quotes = set()
for m in re.finditer(r'"([^"\n]{6,400})"', md):
    quotes.add(m.group(1))
for m in re.finditer(r'`([^`\n]{6,300})`', md):
    quotes.add(m.group(1))

missing_cluster, missing_all, ok = [], [], 0
for q in sorted(quotes):
    parts = [p for p in re.split(r"\s*(?:\.\.\.|…)\s*", q) if len(p) >= 6]
    if not parts:
        continue
    def found(blob):
        return all(norm(p) in blob for p in parts)
    if found(blob_cluster):
        ok += 1
    elif found(blob_all):
        missing_cluster.append(q)
    else:
        missing_all.append(q)

print(f"{name}: quoted strings checked={ok+len(missing_cluster)+len(missing_all)} exact-in-cluster={ok} "
      f"in-other-cluster={len(missing_cluster)} NOT-FOUND={len(missing_all)}")
for q in missing_cluster:
    print("  [other-cluster]", q[:140])
for q in missing_all:
    print("  [NOT FOUND]", q[:140])
