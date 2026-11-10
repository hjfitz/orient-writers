#!/usr/bin/env python3
"""Lint a plainly draft. Checks the prose for fluff, punctuation and spelling, and, given the
source, lists anything the rewrite dropped or changed.

Usage:
  python3 lint.py draft.md [--source original.md] [--us] [--max-words 25] [--step-words 20]
  python3 lint.py - < draft.md

Prose checks skip fenced code, inline code and URLs. They run per paragraph, so a phrase split
by a hard wrap is still caught.

With --source, these must survive the rewrite: fenced code blocks (relative indentation kept),
inline code, link targets (URLs, relative paths, #anchors, [[wiki links]]), front matter lines,
ticket keys, code-like identifiers (snake_case, camelCase, --flags, file paths), and numbers in
the prose along with any time, size or percentage unit. It can't see indented code blocks, or
links into the page from elsewhere.

Exit 1: errors (em dashes) or anything from the source missing in the draft.
Exit 2: an input couldn't be read. Warnings are judgement calls: fix them unless there is a reason.
"""
import argparse, re, sys, textwrap

FILLER = [  # (pattern, advice); matched case-insensitively against each paragraph
    (r"\bit(?:'s| is) (?:worth noting|important to note|worth mentioning) that\b", "cut"),
    (r"\bit should be noted\b", "cut"),
    (r"\b(?:please )?note that\b", "cut, or just say it"),
    (r"\bas (?:mentioned|noted|discussed|stated|described) (?:above|below|earlier|previously)\b", "cut, or link"),
    (r"\bthis (?:document|page|section|guide) (?:describes|outlines|explains|covers|aims to|will)\b", "say it instead"),
    (r"\bin this (?:document|page|section|guide),? (?:we|you)\b", "say it instead"),
    (r"\bin summary\b|\bin conclusion\b|\bto summari[sz]e\b|(?:^|(?<=[.!?] ))overall,", "cut the recap"),
    (r"\bin order to\b", "to"),
    (r"\bdue to the fact that\b", "because"),
    (r"\bat this (?:point|moment) in time\b", "now"),
    (r"\bprior to\b", "before"),
    (r"\bsubsequent to\b", "after"),
    (r"\bin the event that\b", "if"),
    (r"\bfor the purpose of\b", "to, or for"),
    (r"\bwith regards? to\b|\bwith respect to\b", "about, or for"),
    (r"\ba (?:large |significant )?number of\b", "many, or the number"),
    (r"\b(?:is|are) able to\b|\b(?:has|have) the ability to\b", "can"),
    (r"\butili[sz](?:e|es|ed|ing|ation)\b", "use"),
    (r"\bleverag(?:e|es|ed|ing)\b", "use"),
    (r"\bfacilitat(?:e|es|ed|ing)\b", "help, or let"),
    (r"\bmake a decision\b", "decide"),
    (r"\b(?:carry|carries|carried|carrying) out (?:a|an) \w+ of\b", "use the verb"),
    (r"\bperform(?:s|ed|ing)? (?:a|an) \w+ of\b", "use the verb"),
    (r"\b(?:going|moving) forward\b", "from now on, or cut"),
    (r"\b(?:very|really|extremely|incredibly)\b", "cut, or use a precise word"),
    (r"\b(?:basically|essentially|simply)\b", "cut"),
    (r"\b(?:robust|seamless(?:ly)?|powerful|cutting-edge|state-of-the-art|best-in-class|world-class)\b", "puffery: say what it does"),
    (r"\b(?:crucial|vital)\b", "say what happens if it's ignored"),
    (r"\blet's\b|\blet us\b", "address the reader directly"),
    (r"\bdeep dive\b|\bdive (?:in|into|deeper)\b", "cut"),
]
HEDGES = r"\b(?:may|might|could|can)\s+(?:potentially|possibly|perhaps|conceivably)\b|\bpotentially\s+(?:may|might|could)\b|\bit is possible that\b[^.]*\b(?:may|might|could)\b"
US_SPELLING = (
    r"\b(?:behavior\w*|colors?|colored|favor(?:s|ed|ite|ites)?|honor\w*|labor\w*|centers?|centered"
    r"|organiz\w*|prioritiz\w*|realiz\w*|recogniz\w*|summariz\w*|optimiz\w*|minimiz\w*|maximiz\w*"
    r"|standardiz\w*|categoriz\w*|analyz\w*|catalogs?|defense|canceled|canceling|modeled|modeling|traveled)\b"
)
DASH = r"—|\s–\s"
OBLIGATION = {  # counted case-insensitively in prose, longer forms first
    "must not": r"\bmust not\b|\bmustn't\b",
    "must": r"\bmust\b(?! not)",
    "should not": r"\bshould not\b|\bshouldn't\b",
    "should": r"\bshould\b(?! not)",
    "may": r"(?<!\d )\bmay\b(?! \d)",
    "can't": r"\bcannot\b|\bcan't\b|\bcan not\b",
    "never": r"\bnever\b",
    "do not": r"\bdo not\b|\bdon't\b",
    "only": r"\bonly\b",
    "required": r"\brequired?\b",
}
NEGATIONS = ("must not", "should not", "can't", "never", "do not")
IDENTIFIERS = [
    r"\b[A-Z][A-Z0-9]+-\d+\b",                                   # ticket keys
    r"\b[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+\b",                       # snake_case
    r"\b[a-z]+(?:[A-Z][a-z0-9]*)+\b",                            # camelCase
    r"(?:(?<=\s)|^)--?[A-Za-z][\w-]*",                           # --flags
    r"(?<![\w/.~])(?:~|\.{1,2})?/[\w.-]+(?:/[\w.-]+)*",          # /abs, ./rel, ~/home paths
    r"\b[\w-]+(?:/[\w.-]+)+\.\w+\b",                             # dir/file.ext
    r"\b[\w-]+\.(?:md|ya?ml|json|py|sh|ts|js|tf|go|toml|txt|csv|sql|env)\b",
]
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,:/-]\d+)*")
NUM_UNIT = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)*)\s?(%|per ?cent\b|(?:milliseconds?|ms|seconds?|secs?|s|minutes?|mins?|m"
    r"|hours?|hrs?|h|days?|d|weeks?|wks?|w|months?|years?|yrs?|y|[kmgtp]i?b)\b)", re.I)
UNITS = {"ms": "ms millisecond milliseconds", "s": "s sec secs second seconds",
         "min": "m min mins minute minutes", "h": "h hr hrs hour hours", "d": "d day days",
         "w": "w wk wks week weeks", "month": "month months", "y": "y yr yrs year years",
         "%": "% percent"}
ABBREV = re.compile(r"\b(e\.g|i\.e|etc|vs|approx|incl|cf|no)\.", re.I)
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
ORDERED = re.compile(r"^\s*\d+[.)]\s+")
URL = re.compile(r"https?://[^\s)>\]`\"']+")
LINK_TARGET = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|\[\[([^\]]+)\]\]|^\s*\[[^\]]+\]:\s*(\S+)", re.M)
FENCE = re.compile(r"^\s*(```|~~~)")


def parse(text):
    """Split markdown into front matter, prose lines (with line numbers) and fenced code blocks."""
    lines = text.splitlines()
    start, front = 0, []
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                front = [l.strip() for l in lines[1:i] if l.strip()]
                start = i + 1
                break
    prose, blocks, block, fence = [], [], None, None
    for n, line in enumerate(lines[start:], start + 1):
        m = FENCE.match(line)
        if block is not None:
            if m and m.group(1) == fence:
                blocks.append(textwrap.dedent("\n".join(l.rstrip() for l in block)).strip("\n"))
                block = None
            else:
                block.append(line)
            continue
        if m:
            block, fence = [], m.group(1)
            continue
        prose.append((n, line))
    raw = "\n".join(l for _, l in prose)
    return {
        "front": front,
        "prose": prose,
        "units": units(prose),
        "blocks": [b for b in blocks if b.strip()],
        "inline": set(re.findall(r"`([^`\n]+)`", raw)),
        "urls": {u.rstrip(".,;:") for u in URL.findall(text)},
        "targets": {t for g in LINK_TARGET.findall(raw) for t in g if t and not t.startswith("http")},
    }


def clean(line):
    """Strip the parts of a line that aren't prose."""
    line = re.sub(r"<!--.*?-->", "", line)
    line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)        # images
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)     # links keep their text
    line = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", line)  # wiki links keep their label
    line = re.sub(r"`[^`\n]*`", "", line)
    return URL.sub("", line)


def units(prose):
    """Prose as checkable units of (line, text, kind). Paragraphs and list items are joined across
    hard wraps. Headings and table rows stand alone. kind is para, step (numbered item) or line."""
    out, cur, start, kind = [], [], None, "para"

    def flush():
        nonlocal cur, start
        if cur:
            out.append((start, " ".join(cur), kind))
        cur, start = [], None

    for n, line in prose:
        s = line.strip()
        if not s or re.fullmatch(r"[-*_=\s]{3,}", s):
            flush()
            continue
        if s.startswith(("#", "|")):
            flush()
            out.append((n, clean(s), "line"))
            continue
        if LIST_ITEM.match(line):
            flush()
            kind = "step" if ORDERED.match(line) else "para"
            s = LIST_ITEM.sub("", line).strip()
        elif not cur:
            kind = "para"
        s = re.sub(r"^(?:>\s?)+", "", s).strip()
        if start is None:
            start = n
        cur.append(clean(s))
    flush()
    return out


def sentences(par):
    par = ABBREV.sub(lambda m: m.group(1).replace(".", ""), par)
    return [s for s in re.split(r"(?<=[.!?])\s+", par) if s.strip()]


def words(s):
    return re.findall(r"[A-Za-z0-9][\w'-]*", s)


def prose_text(doc):
    return "\n".join(t for _, t, _ in doc["units"])


def stats(doc):
    sents = [s for _, t, k in doc["units"] if k != "line" for s in sentences(t)]
    mean = sum(len(words(s)) for s in sents) / len(sents) if sents else 0
    return len(words(prose_text(doc))), len(sents), mean


def canon(unit):
    u = unit.lower().replace(" ", "")
    return next((k for k, v in UNITS.items() if u in v.split()), u)


def lint(text, us=False, max_words=25, step_words=20):
    errs, warns = [], []
    doc = parse(text)
    for n, t, kind in doc["units"]:
        if re.search(DASH, t):
            errs.append(f"L{n}  em dash: use a full stop, comma or colon")
        if re.search(r"!(?=\s|$)", t):
            warns.append(f"L{n}  exclamation mark")
        for pat, advice in FILLER:
            for m in re.finditer(pat, t, re.I):
                warns.append(f'L{n}  "{m.group(0)}": {advice}')
        for m in re.finditer(HEDGES, t, re.I):
            warns.append(f'L{n}  stacked hedge "{m.group(0)}": keep one hedge')
        if not us:
            for m in re.finditer(US_SPELLING, t, re.I):
                warns.append(f'L{n}  US spelling "{m.group(0)}" (--us if that is the house style)')
        if kind == "line":
            continue
        limit = min(step_words, max_words) if kind == "step" else max_words
        for s in sentences(t):
            w = len(words(s))
            if w > limit:
                warns.append(f'L{n}  {w}-word sentence (aim for {limit} or fewer): "{" ".join(s.split()[:8])} ..."')
    return doc, errs, warns


def present(token, text):
    return re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", text) is not None


def compare(src, draft, draft_text):
    missing = []
    for line in src["front"]:
        if line not in draft["front"]:
            missing.append(f"front matter line: {line}")
    for b in src["blocks"]:
        if b not in draft["blocks"]:
            missing.append(f"code block changed or dropped: {b.strip().splitlines()[0][:60]}")
    for c in sorted(src["inline"]):
        if c not in draft["inline"] and not present(c, draft_text):
            missing.append(f"inline code `{c}`")
    for u in sorted(src["urls"]):
        if u not in draft_text:
            missing.append(f"URL {u}")
    for t in sorted(src["targets"]):
        if t not in draft_text:
            missing.append(f"link target {t}")
    st = prose_text(src)
    seen = set()
    for pat in IDENTIFIERS:
        for i in re.findall(pat, st):
            if i not in seen and not present(i, draft_text):
                missing.append(f"identifier {i}")
            seen.add(i)
    dt = prose_text(draft)
    sn, dn = set(NUMBER.findall(st)), set(NUMBER.findall(dt))
    for n in sorted(sn - dn, key=lambda x: (len(x), x)):
        missing.append(f"number {n}")
    du = {(m.group(1), canon(m.group(2))) for m in NUM_UNIT.finditer(dt)}
    for n, u in sorted({(m.group(1), canon(m.group(2))) for m in NUM_UNIT.finditer(st)}):
        if n in dn and (n, u) not in du:
            now = sorted({v for k, v in du if k == n}) or ["no unit"]
            missing.append(f"number {n}: unit changed ({u} → {', '.join(now)})")
    a = {k: len(re.findall(p, st, re.I)) for k, p in OBLIGATION.items()}
    b = {k: len(re.findall(p, dt, re.I)) for k, p in OBLIGATION.items()}
    changed = [f"{k} {a[k]} → {b[k]}" for k in OBLIGATION if a[k] != b[k]]
    neg0, neg1 = (sum(c[k] for k in NEGATIONS) for c in (a, b))
    negs = f"fewer negations ({neg0} → {neg1}): check no instruction flipped from don't to do" if neg1 < neg0 else ""
    return missing, changed, negs


def read(path):
    try:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        sys.exit(f"can't read {path}: {e.strerror}")  # exit 2 below via SystemExit message
    if not text.strip():
        print(f"{path}: empty input", file=sys.stderr)
        sys.exit(2)
    return text.replace("\u2019", "'").replace("\u2018", "'")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft", help="the draft, or - for stdin")
    ap.add_argument("--source", help="the original text, for a rewrite")
    ap.add_argument("--us", action="store_true", help="US house style: skip the spelling check")
    ap.add_argument("--max-words", type=int, default=25, help="sentence limit for descriptive text")
    ap.add_argument("--step-words", type=int, default=20, help="sentence limit inside numbered steps")
    a = ap.parse_args()

    try:
        text = read(a.draft)
        src_text = read(a.source) if a.source else None
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            sys.exit(2)
        raise

    doc, errs, warns = lint(text, a.us, a.max_words, a.step_words)
    for e in errs:
        print("ERROR  ", e)
    for w in warns:
        print("warn   ", w)

    missing = []
    w1, s1, m1 = stats(doc)
    if src_text:
        src = parse(src_text)
        missing, changed, negs = compare(src, doc, text)
        for m in missing:
            print("MISSING", m)
        if negs:
            print("WARN   ", negs)
        if changed:
            print("warn    obligation words changed:", ", ".join(changed),
                  "(check nothing was weakened or strengthened; an imperative counts as a must)")
        w0, s0, m0 = stats(src)
        pct = f" ({(w1 - w0) / w0:+.0%})" if w0 else ""
        print(f"info    words {w0} → {w1}{pct}, sentences {s0} → {s1}, mean sentence {m0:.1f} → {m1:.1f} words")
    else:
        print(f"info    words {w1}, sentences {s1}, mean sentence {m1:.1f} words")
    gaps = text.count("[??]")
    if gaps:
        print(f"info    {gaps} gap(s) marked [??]: list each under Author review")

    bad = len(errs) + len(missing)
    print("PASS" if not bad else f"FAIL ({len(errs)} errors, {len(missing)} missing)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
