#!/usr/bin/env python3
"""Lint a Slack draft against the mechanical rules in ~/Documents/obsidian/Voice/Voice.md.

Usage:
  python3 check.py [--register terse|warm|channels] [--swear-ok] <<'EOF'
  first message
  ---
  second message
  EOF
  python3 check.py --json drafts.json [--register ...]   # {"id": {"messages": [...]}} or {"id": [...]}

Errors (hard rules) exit 1. Warnings are judgement calls; fix them unless there is a reason.
"""
import argparse, json, re, sys

ERRORS = [
    ("em/en dash (use ' - ' or a new message)", lambda t: bool(re.search("[—–]", t))),
    ("ends with a full stop", lambda t: t.rstrip().endswith(".") and not t.rstrip().endswith("...")),
    ("Unicode emoji (use :shortcode:)", lambda t: bool(re.search("[\U0001F300-\U0001FAFF☀-➿⭐⬆]", t))),
    ("'into' (he writes 'in to')", lambda t: bool(re.search(r"\binto\b", t, re.I))),
    ("'anyone' (he writes 'anybody')", lambda t: bool(re.search(r"\banyone\b", t, re.I))),
    ("'okay' (he writes 'ok')", lambda t: bool(re.search(r"\bokay\b", t, re.I))),
    ("formal wording", lambda t: bool(re.search(r"\b(regards|kindly|unfortunately|apologies|thank you so much|hope you'?re well|as per|i believe)\b", t, re.I))),
    ("'!!' (never doubled)", lambda t: "!!" in t),
    ("list, heading or bold in a chat reply", lambda t: bool(re.search(r"^\s*([-*•]\s|#{1,6}\s)|\*\*[^*]+\*\*", t, re.M))),
    ("dropped apostrophe (dont, cant, im, ive, thats ...)", lambda t: bool(re.search(r"\b(dont|cant|wont|didnt|doesnt|isnt|arent|wasnt|im|ive|thats|theres|youre|weve|itll)\b", t, re.I))),
    ("American spelling (he writes British: prioritise, realise, behaviour)", lambda t: bool(re.search(r"\b(prioritiz\w*|realiz\w*|standardiz\w*|behavior\w*|organiz\w*)\b", t, re.I))),
]

SWEAR = re.compile(r"\b(fuck\w*|shit\w*|piss\w*|wank\w*|bollocks|arse\w*|bugger\w*|damn\w*|tits)\b", re.I)
EMOJI = re.compile(r":[a-z0-9_+\-]+:")
WRAPPERS = {
    "promise to check/come back": r"\b(let me|i'll|i will|will)\b.{0,25}\b(check|look|dig|come back|find out|take a look|double check|get back)",
    "shout": r"\bshout\b",
    "thanks/cheers/ta": r"\b(cheers|thanks|ta|appreciate)\b",
    "praise words": r"\b(nice one|nice work|well done|great|fab|brill|perfect)\b",
}


def split_messages(text):
    return [m.strip() for m in re.split(r"^\s*---\s*$", text, flags=re.M) if m.strip()]


def check(messages, register=None, swear_ok=False):
    errs, warns = [], []
    for n, m in enumerate(messages, 1):
        for label, f in ERRORS:
            if f(m):
                if label.startswith("ends with a full stop") and register == "channels":
                    warns.append(f"msg {n}: {label} (3% of channel messages do; fine only for a long explanation)")
                else:
                    errs.append(f"msg {n}: {label}")
        if SWEAR.search(m) and not swear_ok:
            errs.append(f"msg {n}: swearing without --swear-ok (see swearing rule in Voice.md)")
        words = len(m.split())
        if words > 25:
            warns.append(f"msg {n}: {words} words (over 25 is rare; split it, or confirm it is an explanation/announcement)")
        if len(EMOJI.findall(m)) > 1:
            warns.append(f"msg {n}: more than one emoji")
        if register == "terse" and re.search(r"\bplease\b", m, re.I):
            warns.append(f"msg {n}: 'please' never appears in the terse register")
        if register == "terse" and words <= 3 and EMOJI.search(m) and not re.fullmatch(r"(:[a-z0-9_+\-]+:\s*)+", m.strip()):
            warns.append(f"msg {n}: emoji on a very short terse message (2% of these carry one)")
    emoji_msgs = sum(bool(EMOJI.search(m)) for m in messages)
    if len(messages) > 1 and emoji_msgs > 1:
        warns.append(f"burst: emoji on {emoji_msgs} of {len(messages)} messages (put at most one, on the last and longest)")
    for label, p in WRAPPERS.items():
        c = sum(bool(re.search(p, m, re.I)) for m in messages)
        if c > 1 or (label in ("promise to check/come back", "shout") and c == 1):
            warns.append(f"stock wrapper '{label}' x{c} (real rate under 1 per 100 messages for promise/shout; allow one wrapper, and only if the thread calls for it)")
    wrapper_total = sum(any(re.search(p, m, re.I) for p in WRAPPERS.values()) for m in messages)
    if wrapper_total > 1:
        warns.append(f"{wrapper_total} messages carry a stock wrapper (use at most one per reply)")
    if len(messages) > 3:
        warns.append(f"{len(messages)} messages in the burst (usually 1 to 3)")
    return errs, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", choices=["terse", "warm", "channels"])
    ap.add_argument("--swear-ok", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    bad = 0
    if a.json:
        data = json.load(open(a.json))
        for k, v in data.items():
            msgs = v["messages"] if isinstance(v, dict) else v
            errs, warns = check(msgs, a.register, a.swear_ok)
            if errs or warns:
                print(f"{k}:")
                for e in errs:
                    print("  ERROR", e)
                for w in warns:
                    print("  warn ", w)
            bad += len(errs)
        print(f"\n{len(data)} drafts, {bad} errors")
    else:
        msgs = split_messages(sys.stdin.read())
        if not msgs:
            print("no draft given on stdin")
            sys.exit(2)
        errs, warns = check(msgs, a.register, a.swear_ok)
        for e in errs:
            print("ERROR", e)
        for w in warns:
            print("warn ", w)
        print("PASS" if not errs else f"FAIL ({len(errs)} errors)")
        bad = len(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
