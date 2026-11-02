import os, json,re,statistics,sys
n_=sys.argv[1]
rs=[json.loads(l) for l in open(f'cluster-{n_}.jsonl')]
t=[r['text'] for r in rs]; n=len(t)
w=sorted(len(x.split()) for x in t)
prose=[x for x in t if re.match(r"[A-Za-z]",x)]
sw=re.compile(r"\b(fuck\w*|shit\w*|piss\w*|wank\w*|motherfuck\w*|bollocks|arse\w*)\b",re.I)
emo=re.compile(r":[a-z0-9_+\-]+:")
print(f"{n_}: n={n} days={len({r['date'] for r in rs})} median={statistics.median(w)} p90={w[int(n*.9)-1]} le3w={sum(len(x.split())<=3 for x in t)/n:.0%} gt25w={sum(len(x.split())>25 for x in t)}")
print(f"  lower-start(prose)={sum(x[0].islower() for x in prose)/len(prose):.1%} '!'={sum('!' in x for x in t)/n:.1%} '?'={sum('?' in x for x in t)/n:.1%} emoji={sum(bool(emo.search(x)) for x in t)/n:.1%} endstop={sum(x.rstrip().endswith('.') for x in t)} swear={sum(bool(sw.search(x)) for x in t)/n:.1%} multiline={sum(chr(10) in x for x in t)/n:.1%}")
