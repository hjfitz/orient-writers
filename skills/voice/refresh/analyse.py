import os, json, glob, re, collections, statistics

D = (os.environ.get("VOICE_WORK") or os.getcwd()).rstrip("/") + "/"
rows = []
for f in sorted(glob.glob(D + "corpus-*.jsonl")):
    for l in open(f):
        rows.append(json.loads(l))

TEMPLATED = re.compile(r"^(Deploying |Reverted dev to master|PR for |haude[, ])", re.I)
def is_human(r):
    if r["agent_suspect"]:
        return False
    if TEMPLATED.match(r["text"]):
        return False
    if r["ch"] in ("#real-agent-only", "#agents-only"):
        return False
    if r["ch"] == "DM:self" or r["ch"] == "DM:Harry Fitzgerald":
        return False
    return True

human = [r for r in rows if is_human(r)]
print(f"rows={len(rows)} human={len(human)}")

def words(t): return re.findall(r"\S+", t)

def audience(r):
    ch = r["ch"]
    reports = ("Matt Shaw", "Nylah Klasson", "Harry Humby", "Schuster Efigenio")
    if ch.startswith("DM:"):
        n = ch[3:]
        if n in reports: return "DM report"
        if n == "Oli Denton": return "DM Oli (boss)"
        if n == "Jack Bailey": return "DM Jack (PM peer)"
        return "DM other"
    if ch.startswith("GDM:"):
        return "GDM"
    return "channel"

print("\nAudience split:", collections.Counter(audience(r) for r in human))

# first word / openers
def first_tok(t):
    w = words(t)
    return re.sub(r"[^\w']", "", w[0].lower()) if w else ""
print("\nTop first words (all human):")
print(collections.Counter(first_tok(r["text"]) for r in human).most_common(40))

# whole-message frequent short replies
short = collections.Counter(r["text"].strip().lower() for r in human if len(words(r["text"])) <= 4)
print("\nMost frequent <=4-word messages:")
print(short.most_common(45))

# emoji shortcodes
em = collections.Counter()
for r in human:
    for m in re.findall(r":[a-z0-9_+\-]+:", r["text"]):
        em[m] += 1
print("\nEmoji shortcodes:", em.most_common(25))

# distinctive words vs generic
stop = set("the a an and or to of in on for is it that this we i you be are was with as at by so but not have has had can will do did if me my our your they them their there then than just up out what when which who how its it's i'm i've i'll don't doesn't can't".split())
wc = collections.Counter()
for r in human:
    for w in words(r["text"].lower()):
        w = re.sub(r"[^\w'\-]", "", w)
        if w and w not in stop and not w.startswith("http") and len(w) > 2:
            wc[w] += 1
print("\nTop content words:", wc.most_common(80))

# British/casual markers
markers = ["cheers","mate","bud","fab","ta ","lovely","nice one","no worries","sounds good","sounds great","spot on","ace","legend","cracking","brilliant","happy to","makes sense","good shout","fair","yeah","yep","yes","nope","haha","lol","heh","hmm","ah ","oh ","cool","awesome","great","thanks","thank you","ta!","appreciate","sorry","apologies","unfortunately","please","pls","fyi","tbh","imo","afaik","i think","i believe","i reckon","probably","might","maybe","should","let me know","shout","bear with","sec","one sec","give me","will do","on it","looking","take a look","poke","chuck","bit of","a bit","reckon","quick","fwiw","ok","okay","sure","gotcha","got it","right","perfect","good stuff","nice","sweet","brill","top","dont","don't","cant","can't"]
mc = collections.Counter()
low = [r["text"].lower() for r in human]
for t in low:
    for m in markers:
        if re.search(r"(?<![a-z])" + re.escape(m.strip()) + r"(?![a-z])", t):
            mc[m.strip()] += 1
print("\nMarker phrase counts (messages containing):", mc.most_common(60))

# by audience stats
def stats(rs, label):
    if not rs: return
    w = [len(words(r["text"])) for r in rs]; t = [r["text"] for r in rs]; n = len(rs)
    print(f"{label:18s} n={n:5d} med={statistics.median(w):4.1f} mean={statistics.mean(w):5.1f} "
          f"lower={sum(x[:1].islower() for x in t)/n:4.0%} '!'={sum('!' in x for x in t)/n:4.0%} "
          f"'?'={sum('?' in x for x in t)/n:4.0%} emoji={sum(bool(re.search(r':[a-z0-9_+-]+:', x)) for x in t)/n:4.0%} "
          f"period_end={sum(x.rstrip().endswith('.') for x in t)/n:4.0%} multi={sum(chr(10) in x for x in t)/n:4.0%}")
print()
by = collections.defaultdict(list)
for r in human: by[audience(r)].append(r)
for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])): stats(v, k)
print()
for ch, c in collections.Counter(r["ch"] for r in human).most_common(18):
    stats([r for r in human if r["ch"] == ch], ch[:18])

# time-drift: lowercase ratio and length by quarter
print()
q = collections.defaultdict(list)
for r in human:
    y, m = r["date"][:4], int(r["date"][5:7])
    q[f"{y}Q{(m-1)//3+1}"].append(r)
for k in sorted(q): stats(q[k], k)

json.dump(human, open(D + "human.json", "w"))
