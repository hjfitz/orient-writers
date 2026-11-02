#!/usr/bin/env python3
"""Waypoint — deterministic state/context helper for the waypoint-* skills.

Everything Waypoint owns lives in the Obsidian vault. This script never writes
to a code repository (it does `git fetch` to refresh remote-tracking refs).

Exit codes: 0 ok · 1 usage/fatal (`die`) · 2 `signoff` BLOCKED / `doctor` has
gating findings · 3 `stale` found a doc behind its anchor.
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

VAULT = Path(os.environ.get("WAYPOINT_VAULT", Path.home() / "Documents/obsidian"))
ENG = VAULT / "Engineering"
# One level above a service. Services stay flat under Engineering/ -- locate() resolves
# ENG/<name>, every doc's verified_paths is repo-relative and every wikilink is by folder
# name, so nesting them would be a migration with no upside. A service declares its system
# in waypoint.yaml (`system:`) instead, and that declaration is the only source of truth for
# membership; Systems/<name>/ carries the docs, never a member list to drift from it.
SYS = VAULT / "Systems"
SYSTEM_DOCS = ["overview.md", "architecture.md", "known-context.md", "design.md"]
REPO_ROOTS = [Path(os.environ.get("WAYPOINT_REPOS", Path.home() / "code/fuse"))]
# Multi-repo programmes (a migration, a rewrite) live outside Engineering/ because they are not
# one service. Their state docs are identified by the `migration-state` tag, not by folder.
PROGRAMMES = Path(os.environ.get("WAYPOINT_PROGRAMMES", VAULT / "Bifrost"))
PROGRAMME_TAG = "migration-state"
PROGRAMME_DONE = re.compile(r"complete|done|abandoned|shipped|closed", re.I)
TEMPLATES = Path(__file__).parent / "templates"
# The durable per-service docs. Filename IS the doc kind; orient mirrors this list in
# src/domain/types.ts (WAYPOINT_DOC_KINDS) to render them, so add to both or a new doc
# lands as "other" there. design.md is expected on a `type: frontend` service (and on a
# library that ships UI, e.g. ui-toolkit) — the house design language, anchored to the
# token/component paths so `wp stale` catches a design system moving under the doc.
DEFAULT_DOCS = ["overview.md", "architecture.md", "known-context.md", "operations.md", "testing.md", "interfaces.md", "design.md"]
NON_DOC_FILES = {"ledger.md", "ideas-log.md"}  # agent-facing logs, not durable docs — own display, no staleness anchor
TODAY = dt.date.today().isoformat()
OPEN_STATUSES = ("draft", "active", "blocked")


# ---------------------------------------------------------------- shell helpers

def sh(args, cwd=None, check=False):
    if cwd is not None and not Path(cwd).is_dir():
        return 127, "", "no such directory: %s" % cwd
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        return 127, "", "not found: %s" % args[0]
    if check and p.returncode != 0:
        die("command failed: %s\n%s" % (" ".join(args), p.stderr.strip()))
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def die(msg, code=1):
    print("wp: %s" % msg, file=sys.stderr)
    sys.exit(code)


def warn(msg):
    print("wp: %s" % msg, file=sys.stderr)


# Durable records sync with the vault, one directory per machine so each file has one writer and git
# never merges it (matches orient's config.ts recordsDir/hostId). The machine id is a file, not env,
# because this runs under Claude Code rather than orient's units.
HOST_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def orient_host_id():
    try:
        p = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "orient" / "host"
        hid = p.read_text().strip()
        if HOST_ID.match(hid):
            return hid
    except OSError:
        pass
    return "laptop"


def orient_records_dir():
    base = os.environ.get("ORIENT_RECORDS_DIR")
    root = Path(base) if base else VAULT / ".knowledge" / "records"
    return root / orient_host_id()


# Appends one row per tick to plan-usage.jsonl: which session/effort actually did the work,
# against what the plan recommended at tick time. orient joins this by session_id against
# statusline.py's usage-history.jsonl (session_id -> model/cost over time) to show recommended-vs-
# actual on the Usage page. Fully guarded — a write failure never blocks the tick itself.
def record_plan_usage(service, plan_stem, increment, fm):
    try:
        d = orient_records_dir()
        d.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": int(dt.datetime.now().timestamp()),
            "service": service,
            "plan": plan_stem,
            "increment": str(increment),
            "session_id": os.environ.get("CLAUDE_CODE_SESSION_ID"),
            "effort_env": os.environ.get("CLAUDE_EFFORT"),
            "recommended_model": fm.get("impl_model"),
            "recommended_effort": fm.get("impl_effort"),
        }
        with open(d / "plan-usage.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


# Appends one row per ledger entry and programme tick to work-usage.jsonl, so orient can price
# out-of-ticket and programme work by session the way plan-usage.jsonl prices plan work. Fully
# guarded — a write failure never blocks the ledger entry or the tick.
PR_REF = re.compile(r"\b([A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*#\d+)\b")


def record_work_usage(kind, **fields):
    try:
        d = orient_records_dir()
        d.mkdir(parents=True, exist_ok=True)
        row = {"ts": int(dt.datetime.now().timestamp()), "kind": kind,
               "session_id": os.environ.get("CLAUDE_CODE_SESSION_ID")}
        row.update(fields)
        with open(d / "work-usage.jsonl", "a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


# ------------------------------------------------------------------ safe i/o

_READ_MTIME = {}   # resolved path -> st_mtime_ns when this process last read it


def atomic_write(path: Path, text: str):
    """Same-directory temp file + os.replace, so a reader never sees a half-written file and a
    crash mid-write cannot truncate one. Replaces the mtime this process remembers for the path."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".wp-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _remember(path)


def _remember(path: Path):
    try:
        _READ_MTIME[str(path.resolve())] = path.stat().st_mtime_ns
    except OSError:
        pass


def changed_since_read(path: Path) -> bool:
    """True when someone else wrote this file after we read it. Several sessions edit one vault;
    a read-modify-write that spans a network call would otherwise silently revert their edit."""
    seen = _READ_MTIME.get(str(path.resolve()))
    if seen is None:
        return False
    try:
        return path.stat().st_mtime_ns != seen
    except OSError:
        return False


CONFLICT = ("%s changed on disk since it was read (another session?) — nothing written. "
            "Re-run this command.")


# ------------------------------------------------------------- frontmatter i/o

FM = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.S)
STR_KEYS = ("verified_sha", "base_sha", "pr", "ticket")   # PyYAML types digit-only values as numbers
DATE_KEYS = ("created", "updated", "verified")            # PyYAML types unquoted ISO dates as date objects


def load_fm(path: Path):
    """Lowest level, never raises -> (data, body, error, raw_frontmatter_text).
    data is the dict exactly as PyYAML typed it; None when the block failed to parse.
    error is None, "no frontmatter block", "frontmatter is not a mapping", or the YAML message."""
    if not path.exists():
        return {}, "", "no such file", ""
    text = path.read_text()
    _remember(path)
    m = FM.match(text)
    if not m:
        return {}, text, "no frontmatter block", ""
    raw = m.group(1)
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        return None, m.group(2), (str(e).strip().splitlines() or ["yaml error"])[0], raw
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, m.group(2), "frontmatter is not a mapping", raw
    return data, m.group(2), None, raw


def _raw_token(raw: str, key: str):
    m = re.search(r"^%s:[ \t]*([^\s#]+)" % re.escape(key), raw, re.M)
    return m.group(1).strip("'\"") if m else None


def norm_fm(fm: dict, raw: str = "") -> dict:
    """Coerce PyYAML-typed scalars back to the strings every caller assumes."""
    for k in STR_KEYS:
        v = fm.get(k)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            fm[k] = _raw_token(raw, k) or str(v)
    for k in DATE_KEYS:
        v = fm.get(k)
        if isinstance(v, (dt.date, dt.datetime)):
            fm[k] = v.isoformat()[:10]
        elif v is not None and not isinstance(v, str):
            fm[k] = str(v)
    return fm


def read_fm(path: Path):
    """Tolerant: ({}, body) on any failure. Values normalised to strings."""
    data, body, err, raw = load_fm(path)
    if data is None:
        return {}, body
    return norm_fm(data, raw), body


def read_fm_strict(path: Path):
    """For writers: (fm, body, error). error is set only when a frontmatter block exists and
    does not parse — a doc with no block at all is fine (the writer adds one)."""
    data, body, err, raw = load_fm(path)
    if data is None:
        return {}, body, err
    return norm_fm(data, raw), body, None


def fm_error(path: Path):
    err = load_fm(path)[2]
    return None if err in (None, "no frontmatter block") else err


def write_fm(path: Path, data: dict, body: str, on_conflict="die"):
    """on_conflict="die" for a single-file command; "skip" for a sweep, which returns False and
    carries on rather than abandoning the remaining files."""
    if changed_since_read(path):
        if on_conflict == "die":
            die(CONFLICT % rel(path))
        warn(CONFLICT % rel(path))
        return False
    fm = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True).strip()
    atomic_write(path, "---\n%s\n---\n%s" % (fm, body.lstrip("\n")))
    return True


# ------------------------------------------------------------------- locating

def canonical_repo(name: str):
    """Map a worktree/side-clone directory name back to its canonical repo."""
    parts = name.split("-")
    while parts:
        cand = "-".join(parts)
        for root in REPO_ROOTS:
            if (root / cand).is_dir():
                return cand, root / cand
        parts.pop()
    return name, None


def repo_override(service: str):
    """`repo:` in a service's waypoint.yaml — for a vault service whose code lives in a
    differently-named repo (e.g. an app inside a monorepo, or an archived standalone
    checkout that must not be used)."""
    wy = ENG / service / "waypoint.yaml"
    if not wy.exists():
        return None
    try:
        meta = yaml.safe_load(wy.read_text()) or {}
    except yaml.YAMLError:
        return None
    r = meta.get("repo") if isinstance(meta, dict) else None
    if not r:
        return None
    p = Path(str(r)).expanduser()
    # A bare name is a repo name, not a cwd-relative path — resolving it against cwd returns a
    # relative Path that every later `git -C` call then interprets from wherever it happens to run.
    if p.is_absolute() and p.is_dir():
        return p
    for root in REPO_ROOTS:
        if (root / str(r)).is_dir():
            return (root / str(r)).resolve()
    return p if p.is_dir() else None


def locate(target=None):
    repo = None
    if target:
        # A bare service name resolves through the vault's own `repo:` declaration BEFORE the
        # filesystem. Treating it as a path first meant the override was silently skipped
        # whenever cwd happened to contain a same-named directory — which is always, from
        # ~/code/fuse, and is why snap-queue-polling-service anchored against the archived
        # standalone checkout instead of the monorepo it actually lives in.
        bare = not any(c in str(target) for c in "/\\") and not str(target).startswith(("~", "."))
        ov = repo_override(target) if bare else None
        if ov is not None:
            d = ENG / target
            return {"service": target, "repo": str(ov), "vault": str(d),
                    "onboarded": (d / "waypoint.yaml").exists()}
        p = Path(target).expanduser()
        if p.is_dir():
            repo = p
        else:
            for root in REPO_ROOTS:
                if (root / target).is_dir():
                    repo = root / target
                    break
            if repo is None:
                name, path = canonical_repo(target)
                repo = path
                if repo is None:
                    # unknown service: still allow vault-only operation
                    return {"service": target, "repo": None, "vault": str(ENG / target),
                            "onboarded": (ENG / target / "waypoint.yaml").exists()}
    else:
        repo = Path.cwd()

    rc, top, _ = sh(["git", "rev-parse", "--show-toplevel"], cwd=repo)
    if rc == 0 and top:
        rc2, common, _ = sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=repo)
        if rc2 == 0 and common:
            main_checkout = Path(common).parent
        else:
            main_checkout = Path(top)
        repo = main_checkout
    service, canon = canonical_repo(repo.name)
    if canon:
        repo = canon
    d = ENG / service
    return {"service": service, "repo": str(repo), "vault": str(d),
            "onboarded": (d / "waypoint.yaml").exists()}


def resolve(args_service):
    info = locate(args_service)
    if not info["service"]:
        die("could not resolve a service; pass one explicitly")
    return info


def iter_programmes():
    """(name, path, fm, error) for every programme state doc — any md under PROGRAMMES whose
    frontmatter tags carry `migration-state`. Folder names are prose with spaces, so the tag is the
    discriminator, not the path."""
    out = []
    if not PROGRAMMES.is_dir():
        return out
    for d in sorted(p for p in PROGRAMMES.iterdir() if p.is_dir()):
        for f in sorted(d.glob("*.md")):
            data, _, err, raw = load_fm(f)
            if data is None:
                if err and PROGRAMME_TAG in f.read_text()[:2000]:
                    out.append((d.name, f, {}, err))
                continue
            tags = data.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]
            tags = [str(x) for x in tags]
            # `migration-state` as a literal missed `remediation-state` entirely — a sixth
            # programme sat invisible to STALE-PROGRAMME because of a string comparison.
            if any(x == PROGRAMME_TAG or x.endswith("-state") for x in tags) or data.get("programme"):
                out.append((d.name, f, norm_fm(dict(data), raw), None))
    return out


def iter_services():
    if not ENG.is_dir():
        return []
    return sorted(((p.name, p) for p in ENG.iterdir() if p.is_dir()), key=lambda t: t[0])


def iter_systems():
    if not SYS.is_dir():
        return []
    return sorted(((p.name, p) for p in SYS.iterdir() if p.is_dir()), key=lambda t: t[0])


def system_of(service_dir: Path):
    """The system a service declares in waypoint.yaml. None when it declares none."""
    wy = service_dir / "waypoint.yaml"
    if not wy.exists():
        return None
    try:
        data = yaml.safe_load(wy.read_text()) or {}
    except Exception:
        return None
    v = data.get("system")
    return str(v).strip() if v else None


def system_members(name: str):
    """Derived, never stored: a service is a member because its own waypoint.yaml says so.
    A stored list in system.yaml would be a second source of truth and would silently rot
    every time a service is onboarded."""
    return [(s, d) for s, d in iter_services() if system_of(d) == name]


def rel(path: Path):
    try:
        return str(path.relative_to(ENG))
    except ValueError:
        return str(path)


def rel_vault(path: Path):
    try:
        return str(path.relative_to(VAULT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------- stale

def fetch_origin(repo):
    """Best-effort refresh of origin's remote-tracking refs before comparing anything
    against them — without this, "0 commits since" can just mean "haven't fetched
    recently," not "actually current." Silent on failure (offline, no remote): whatever
    refs are already local get used as-is, same as before this existed."""
    if repo and Path(repo).is_dir():
        sh(["git", "fetch", "origin"], cwd=repo)


_DEFAULT_REF_CACHE = {}


def default_branch_ref(repo: Path):
    """origin's default branch as a local remote-tracking ref, e.g. 'origin/master'.
    Never the checked-out branch — a main checkout left on a stale/dangling feature
    branch must not silently understate (or misattribute) doc staleness."""
    key = str(repo)
    if key in _DEFAULT_REF_CACHE:
        return _DEFAULT_REF_CACHE[key]
    ref = _resolve_default_branch(repo)
    _DEFAULT_REF_CACHE[key] = ref
    return ref


def _resolve_default_branch(repo: Path):
    rc, out, _ = sh(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=repo)
    if rc == 0 and out.strip():
        return out.strip()
    # origin/HEAD unset locally. Ask the remote rather than guessing: a repo can carry both
    # `main` and `master` where one is an abandoned stub on a disjoint history (ilg-secure-notes:
    # default is master, `main` is a lone "Initial commit"). Guessing there reports every doc as
    # stale against a branch the work never lands on.
    rc, out, _ = sh(["git", "ls-remote", "--symref", "origin", "HEAD"], cwd=repo)
    if rc == 0:
        m = re.search(r"^ref:\s+refs/heads/(\S+)\s+HEAD", out, re.M)
        if m:
            cand = "origin/%s" % m.group(1)
            if sh(["git", "rev-parse", "--verify", "--quiet", cand], cwd=repo)[0] == 0:
                return cand
    # Offline: prefer whichever candidate has the newest tip over a fixed main-first order.
    dated = []
    for cand in ("origin/main", "origin/master"):
        rc, when, _ = sh(["git", "log", "-1", "--format=%ct", cand], cwd=repo)
        if rc == 0 and when.strip().isdigit():
            dated.append((int(when), cand))
    if dated:
        return max(dated)[1]
    return "HEAD"  # last resort: no remote-tracking ref found at all


def anchor_ancestry(repo: Path, sha: str, ref: str):
    """'ok' | 'off-branch' | 'missing'. An anchor that exists locally but is not an ancestor of the
    default branch — a pre-squash or rebased commit — still produces a plausible `git log sha..ref`
    count, so the doc reads as N commits stale when nothing actually changed. Squash-merging repos
    generate these every time a plan is anchored from the branch instead of after the merge."""
    if not repo or not sha or sha == "unknown":
        return "missing"
    if sh(["git", "cat-file", "-e", "%s^{commit}" % sha], cwd=repo)[0] != 0:
        return "missing"
    if sh(["git", "merge-base", "--is-ancestor", sha, ref], cwd=repo)[0] == 0:
        return "ok"
    return "off-branch"


SNAPSHOT_RE = re.compile(r"\(snapshot (\d{4}-\d{2}-\d{2})[^)]*\)")
SNAPSHOT_DAYS = 60


def snapshots(d: Path):
    """known-context.md is exempt from commit-anchored staleness, and rightly — interview truth
    does not rot on commits. But a large share of what is written there is a dated snapshot of
    mutable external state ("no PR opened yet", "deploys parked since ..."), and an exemption
    reads as a guarantee. A marked claim can be aged without breaking the exemption."""
    f = d / "known-context.md"
    if not f.exists():
        return []
    out = []
    for line in f.read_text().splitlines():
        m = SNAPSHOT_RE.search(line)
        if m:
            try:
                age = (dt.date.today() - dt.date.fromisoformat(m.group(1))).days
            except ValueError:
                continue
            out.append({"date": m.group(1), "age": age, "text": re.sub(r"\s+", " ", line).strip()[:110]})
    return out


def doc_staleness(repo: Path, fm: dict, limit=0):
    """Commits touching a doc's verified_paths since its verified_sha, against origin's
    default branch — not local HEAD, which may sit on an unrelated or dangling branch."""
    sha = str(fm.get("verified_sha") or "")
    paths = fm.get("verified_paths") or []
    if not sha or sha == "unknown" or not repo or not Path(repo).is_dir():
        return None, []
    ref = default_branch_ref(repo)
    args = ["git", "log", "--oneline", "%s..%s" % (sha, ref)]
    if paths:
        args += ["--"] + [str(p) for p in paths]
    rc, out, err = sh(args, cwd=repo)
    if rc != 0:
        return None, []
    lines = [l for l in out.splitlines() if l.strip()]
    return len(lines), lines[:limit] if limit else []


# --------------------------------------------------------------- vault reading

def plan_files(d: Path):
    pd = d / "plans"
    return sorted(pd.glob("*.md")) if pd.is_dir() else []


def explainer_index(d: Path):
    ed = d / "explainers"
    out = []
    if not ed.is_dir():
        return out
    for f in sorted(ed.glob("*.md")):
        fm, body = read_fm(f)
        thesis = fm.get("thesis")
        if not thesis:
            for line in body.splitlines():
                s = line.strip()
                if s.startswith("**TL;DR**"):
                    thesis = s.replace("**TL;DR**", "").lstrip(" —-")
                    break
        out.append((f.stem, (thesis or "").strip()[:160]))
    return out


def ledger_recent(d: Path, n=5):
    f = d / "ledger.md"
    if not f.exists():
        return []
    lines = f.read_text().splitlines()
    out = []
    for i, l in enumerate(lines):
        if not l.startswith("## "):
            continue
        title = next((x.strip() for x in lines[i + 1:i + 4] if x.strip()), "")
        out.append("%s — %s" % (l[3:].strip(), title[:90]))
        if len(out) == n:
            break
    return out


def last_activity(d: Path):
    """Newest of: a ledger entry, or a plan's `updated`. Doc `verified` dates are deliberately
    excluded — they are all stamped at onboarding, so including them makes every row read the
    same day and the column says nothing."""
    dates = []
    led = ledger_recent(d, 1)
    if led:
        dates.append(led[0].split(" — ")[0].strip())
    for f in plan_files(d):
        fm, _ = read_fm(f)
        if fm.get("updated"):
            dates.append(str(fm["updated"])[:10])
    dates = [x for x in dates if re.match(r"^\d{4}-\d{2}-\d{2}$", x)]
    return max(dates) if dates else "—"


GUARD_RE = re.compile(r"^\s*[-*]\s*\[(\w+):(\w+)\]\s*(.+?)(?:\s*—\s*paths:\s*(.+?))?\s*$")
GUARD_CAP = 6


def guardrails(d: Path):
    """Constraints promoted out of prose into something a tool can push at you *before* the
    mistake. They live at the top of architecture.md, which `waypoint-refresh` already maintains
    — known-context.md is exempt from anchors by design, so a path-tagged, checkable list there
    would have no writer able to fix a dead path."""
    f = d / "architecture.md"
    if not f.exists():
        return []
    sec = section(read_fm(f)[1], "Guardrails")
    if not sec:
        return []
    # A guardrail is one bullet, however many lines it wraps over. Parsing line-by-line silently
    # truncated the text and lost the `— paths:` tag, which turned the filter into a pass-through.
    bullets, cur = [], None
    for line in strip_comments(sec).splitlines():
        if re.match(r"^\s*[-*]\s*\[\w+:\w+\]", line):
            if cur:
                bullets.append(cur)
            cur = line.strip()
        elif cur is not None:
            if not line.strip():
                bullets.append(cur); cur = None
            else:
                cur += " " + line.strip()
    if cur:
        bullets.append(cur)
    out = []
    for b in bullets:
        m = GUARD_RE.match(b)
        if m:
            out.append({"kind": m.group(1), "id": m.group(2), "text": m.group(3).strip(),
                        "paths": [x.strip() for x in (m.group(4) or "").split(",") if x.strip()]})
    return out


def guardrails_for(d: Path, paths):
    """Those whose tagged paths intersect the paths in play. An untagged guardrail always shows —
    it has not claimed a scope, so it cannot be ruled out."""
    gs = guardrails(d)
    if not paths:
        return gs
    hit = []
    for g in gs:
        if not g["paths"] or any(str(p).startswith(gp) or gp.startswith(str(p)) for gp in g["paths"] for p in paths):
            hit.append(g)
    return hit


def print_guardrails(gs, where="", limit=GUARD_CAP):
    if not gs:
        return
    print("\n!! GUARDRAILS%s — read before changing anything here" % (" (%s)" % where if where else ""))
    for g in gs[:limit]:
        print("   [%s:%s] %s" % (g["kind"], g["id"], g["text"]))
    if len(gs) > GUARD_CAP:
        print("   !! %d guardrails — the cap is %d. Nobody deletes a guardrail, so a long list "
              "becomes a wall that gets skipped. Prune before adding." % (len(gs), GUARD_CAP))


def ideas_index(d: Path):
    """Every idea ever logged, oldest-safe order (file is newest-first; we return as-is)."""
    f = d / "ideas-log.md"
    if not f.exists():
        return []
    out = []
    for l in f.read_text().splitlines():
        if l.startswith("## "):
            out.append(l[3:].strip())
    return out


# ------------------------------------------------------------- plan body parsing

UNCHECKED_RE = re.compile(r"^\s*[-*] \[ \]")
# Increment ids are not always bare digits — a programme unit reads `W3.`, a split increment
# `1b.` — and rendering those as "?" made the linkage table useless exactly where it mattered.
TICKED_RE = re.compile(r"^\s*[-*] \[[xX]\]\s*(?:([A-Za-z]*\d+[a-z]?)\.)?\s*(.*)$")
# Authors write `— done 2026-09-02: <prose>` and `(commit 32a08cd)`; the strict `done: <sha>` form
# missed both, so four of seven eligible plans had no parseable sha at all. Candidates are
# resolved against the repo before they count, so a hex-looking English word cannot become a
# phantom blocker.
DONE_RE = re.compile(r"\b(?:done|commit)\b[^\n]{0,60}?\b([0-9a-f]{7,40})\b")


def section(body: str, name: str):
    """Content under a heading, up to the next heading at the same or shallower level — so a
    `### Evidence` block stays inside its parent `## Verification` instead of ending it."""
    m = re.search(r"^(#{2,6}) *%s\b" % re.escape(name), body, re.M | re.I)
    if not m:
        return None
    rest = body[m.end():]
    nxt = re.search(r"^#{2,%d} " % len(m.group(1)), rest, re.M)
    return rest[:nxt.start()] if nxt else rest


GATE_RE = re.compile(r"^\s*gate:\s*(.+?)\s*$", re.I)
CONFIRM_RE = re.compile(r"^\s*\[([ xX])\]\s*confirmed\b\s*(.*)$", re.I)
INC_LINE_RE = re.compile(r"^\s*[-*] \[([ xX])\]\s*(?:([A-Za-z]*\d+[a-z]?)\.)?\s*(.*)$")


def parse_increments(inc: str):
    """Each increment with its ticked state and any `gate:` precondition hanging under it.
    A gate is a human precondition, not code — the one thing a fresh session cannot infer from
    the diff, and the reason 'do not action this yet' needs to be structural rather than bold."""
    out, cur = [], None
    for line in (inc or "").splitlines():
        m = INC_LINE_RE.match(line)
        if m:
            cur = {"id": m.group(2) or "?", "ticked": m.group(1).lower() == "x",
                   "text": m.group(3), "gate": None, "confirmed": None, "line": line}
            out.append(cur)
            continue
        if cur is None:
            continue
        g = GATE_RE.match(line)
        if g:
            cur["gate"] = g.group(1)
            continue
        c = CONFIRM_RE.match(line)
        if c and cur["gate"] is not None:
            cur["confirmed"] = c.group(1).lower() == "x"
    return out


def unchecked(text):
    return [l.strip() for l in (text or "").splitlines() if UNCHECKED_RE.match(l)]


def strip_fences(text: str):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def plan_date(fm):
    return str(fm.get("updated") or fm.get("created") or "")


def is_config_only(fm):
    b = str(fm.get("branch") or "").strip()
    w = str(fm.get("worktree") or "").strip().lower()
    return bool(re.match(r"none\b", b, re.I)) or w == "none"


COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def strip_comments(text: str):
    """Template guidance lives in HTML comments: Obsidian hides them, agents read them, and the
    sign-off gate must not see them — otherwise every line of guidance is a mandatory fill, and
    the cheapest way to clear that gate is to delete the guidance."""
    return COMMENT_RE.sub("", text)


MANIFESTS = ("package.json", "pnpm-workspace.yaml", "pnpm-lock.yaml", "mise.toml", "biome.json",
             ".nvmrc", "go.mod", "go.sum", "Makefile", "pyproject.toml", "Cargo.toml",
             "tsconfig.json", "vitest.config.ts", "jest.config.js", "jest.config.ts",
             ".tool-versions", "requirements.txt")


def is_manifest(p: str):
    """The commands anchor exists to fire when the *invocation* changes — a script, an engine, a
    package manager. Anchored to a source directory it fires on every commit and is ignored
    within a week, which is the STALE-DOC failure one axis over."""
    return Path(p).name in MANIFESTS or p.endswith(tuple("/" + m for m in MANIFESTS))


def commands_fm(wy_data: dict):
    """waypoint.yaml's commands block presented as if it were an anchored doc, so it rides the
    existing staleness machinery instead of needing a doctor section of its own."""
    return {"verified": wy_data.get("commands_verified"),
            "verified_sha": wy_data.get("commands_verified_sha"),
            "verified_paths": wy_data.get("commands_verified_paths") or []}


def _template_placeholders():
    tpl = TEMPLATES / "plan.md"
    if not tpl.exists():
        return set()
    return {re.sub(r"\s+", " ", m)
            for m in re.findall(r"<(?!!)[^<>]+>", strip_comments(tpl.read_text()), re.S)}


TEMPLATE_PH = _template_placeholders()
# Placeholder prose: an angle span not glued to an identifier (rules out TS generics like
# Map<host, AxiosInstance>), opening with a letter/paren/quote (rules out <!-- -->, <https://>),
# and containing whitespace (rules out <br>, emails, single-word tags).
PH_RE = re.compile(r"(?<![A-Za-z0-9_\]\)])<(?=[A-Za-z(\"'])[^<>]*?[ \n][^<>]*?>", re.S)


def find_placeholders(body: str):
    text = strip_comments(strip_fences(body))
    found, seen = [], set()
    for m in re.finditer(r"<[^<>]+>", text, re.S):
        if re.sub(r"\s+", " ", m.group(0)) in TEMPLATE_PH:
            found.append(m.group(0))
            seen.add(m.span())
    for m in PH_RE.finditer(text):
        if m.span() not in seen:
            found.append(m.group(0))
            seen.add(m.span())
    return found


def strip_placeholders(s: str):
    s = strip_comments(s)
    for p in find_placeholders(s):
        s = s.replace(p, "")
    return s.strip()


# ------------------------------------------------------------------ PR helpers

def git_cwd_for(fm: dict, info: dict):
    """Where to run git/gh for a plan: its worktree if it still exists, else the repo."""
    wt = str(fm.get("worktree") or "").strip()
    if wt and wt.lower() not in ("none", "unknown") and Path(wt).is_dir():
        return wt
    repo = (info or {}).get("repo")
    return repo if repo and Path(repo).is_dir() else None


def gh_json(args, cwd):
    rc, out, err = sh(["gh"] + args, cwd=cwd)
    if rc != 0:
        return None, (err or out or "gh failed").splitlines()[0][:200]
    try:
        return json.loads(out) if out else [], None
    except ValueError:
        return None, "gh returned non-JSON"


def pr_state(pr, cwd):
    data, err = gh_json(["pr", "view", str(pr), "--json", "number,state,mergedAt,url"], cwd)
    if err:
        return {"error": err}
    return {"number": data.get("number"), "state": data.get("state"),
            "merged": bool(data.get("mergedAt")), "url": data.get("url")}


def discover_pr(branch, cwd, created=None):
    """Newest PR on `branch` created on/after the plan — a branch reused across tickets
    can carry an older, unrelated (and possibly merged) PR that must not count."""
    data, err = gh_json(["pr", "list", "--head", branch, "--state", "all",
                         "--json", "number,state,mergedAt,createdAt,url", "--limit", "5"], cwd)
    if err:
        return {"error": err}
    cands = data or []
    if created:
        c = str(created)[:10]
        cands = [p for p in cands if (p.get("createdAt") or "")[:10] >= c]
    if not cands:
        return None
    p = max(cands, key=lambda x: x.get("createdAt") or "")
    return {"number": p.get("number"), "state": p.get("state"), "merged": bool(p.get("mergedAt")),
            "url": p.get("url"), "createdAt": (p.get("createdAt") or "")[:10], "source": "branch"}


def plan_pr(fm: dict, cwd):
    """-> (pr, source, facts). source: frontmatter | branch | none | error."""
    if fm.get("pr"):
        return str(fm["pr"]), "frontmatter", None
    branch = str(fm.get("branch") or "").strip()
    if not cwd or not branch or branch.lower() in ("unknown", "none") or is_config_only(fm):
        return None, "none", None
    d = discover_pr(branch, cwd, fm.get("created"))
    if d is None:
        return None, "none", None
    if d.get("error"):
        return None, "error", d
    return str(d["number"]), "branch", d


def unclosed_check(fm: dict, info: dict):
    """Shared by status/list/doctor. Never swallows a failure — returns it as `warning`."""
    cwd = git_cwd_for(fm, info)
    if not cwd:
        return {"pr": None, "source": "none",
                "warning": "no repo/worktree dir for %s — cannot check its PR" % (info or {}).get("service")}
    pr, src, facts = plan_pr(fm, cwd)
    if src == "error":
        return {"pr": None, "source": src,
                "warning": "PR discovery failed for branch %s: %s" % (fm.get("branch"), facts.get("error"))}
    if not pr:
        return {"pr": None, "source": "none", "warning": None}
    if not facts:
        facts = pr_state(pr, cwd)
        if facts.get("error"):
            return {"pr": pr, "source": src, "warning": "could not read PR #%s: %s" % (pr, facts["error"])}
    return {"pr": pr, "source": src, "state": facts.get("state"), "merged": bool(facts.get("merged")),
            "url": facts.get("url"), "warning": None}


def dev_deploy_state(fm: dict, cwd):
    """Is the shared dev environment still sitting on this plan's branch? Answered from the real
    deploy history rather than a bookkeeping field, because a field that says "I put it back" can
    lie and the run list cannot. Returns the branch dev is on when it is this plan's, else None."""
    branch = str(fm.get("branch") or "").strip()
    if not cwd or not branch or branch.lower() in ("", "none", "unknown") or is_config_only(fm):
        return None
    data, err = gh_json(["run", "list", "--workflow", "manual-deploy.yaml", "--limit", "8",
                         "--json", "headBranch,conclusion,status,createdAt"], cwd)
    if err or not data:
        return None
    for run in data:  # newest first
        if run.get("conclusion") == "success":
            return branch if run.get("headBranch") == branch else None
    return None


def pr_facts(pr, repo_dir):
    """state/checks/review facts for a PR ref (number or url)."""
    out = {}
    rc, js, err = sh(["gh", "pr", "view", str(pr), "--json",
                      "number,state,isDraft,mergedAt,reviewDecision,statusCheckRollup,url,headRefName,baseRefName"],
                     cwd=repo_dir)
    if rc != 0:
        return {"error": err[:200]}
    data = json.loads(js)
    out["number"] = data.get("number")
    out["state"] = data.get("state")
    out["draft"] = bool(data.get("isDraft"))
    out["merged"] = bool(data.get("mergedAt"))
    out["review"] = data.get("reviewDecision")
    out["url"] = data.get("url")
    failing = [c.get("name") or c.get("context") for c in (data.get("statusCheckRollup") or [])
               if (c.get("conclusion") or c.get("state")) in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "FAILING")]
    pending = [c.get("name") or c.get("context") for c in (data.get("statusCheckRollup") or [])
               if (c.get("conclusion") or c.get("state")) in ("", None, "PENDING", "IN_PROGRESS", "QUEUED")]
    out["failing_checks"] = [f for f in failing if f]
    out["pending_checks"] = [p for p in pending if p]
    q = ('query($n:Int!,$o:String!,$r:String!){repository(owner:$o,name:$r){'
         'pullRequest(number:$n){reviewThreads(first:60){nodes{isResolved isOutdated comments(first:1)'
         '{nodes{author{login} body}}}}}}}')
    rc2, nwo, _ = sh(["gh", "repo", "view", "--json", "owner,name", "-q", '.owner.login+"/"+.name'], cwd=repo_dir)
    if rc2 == 0 and "/" in nwo and out.get("number"):
        owner, name = nwo.split("/", 1)
        rc3, js2, _ = sh(["gh", "api", "graphql", "-f", "query=%s" % q, "-F", "n=%d" % out["number"],
                          "-f", "o=%s" % owner, "-f", "r=%s" % name], cwd=repo_dir)
        if rc3 == 0:
            try:
                nodes = json.loads(js2)["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
                unres = [n for n in nodes if not n.get("isResolved") and not n.get("isOutdated")]
                out["unresolved_threads"] = len(unres)
                out["unresolved_sample"] = [
                    ((n["comments"]["nodes"][0].get("author") or {}).get("login", "?") + ": " +
                     (n["comments"]["nodes"][0].get("body") or "")[:110].replace("\n", " "))
                    for n in unres[:5]]
            except Exception:
                pass
    return out


# ------------------------------------------------------------------- commands

def cmd_locate(a):
    print(json.dumps(locate(a.target), indent=2))


def cmd_init(a):
    info = resolve(a.service)
    d = Path(info["vault"])
    (d / "plans").mkdir(parents=True, exist_ok=True)
    (d / "explainers").mkdir(parents=True, exist_ok=True)
    wy = d / "waypoint.yaml"
    if not wy.exists():
        tpl = (TEMPLATES / "waypoint.yaml").read_text()
        atomic_write(wy, tpl.replace("{{service}}", info["service"]).replace("{{date}}", TODAY))
    led = d / "ledger.md"
    if not led.exists():
        atomic_write(led, "---\ntags: [waypoint, ledger]\n---\n# %s — work ledger\n\n"
                          "Agent-facing. Newest first. What meaningful work happened here, and the\n"
                          "context a future agent needs. Not a diary, not release notes, not a diff.\n\n"
                          % info["service"])
    print("initialised %s\n  repo: %s" % (d, info["repo"]))


def cmd_context(a):
    info = resolve(a.service)
    d = Path(info["vault"])
    repo = Path(info["repo"]) if info["repo"] else None
    fetch_origin(repo)
    print("service: %s | repo: %s | vault: %s | onboarded: %s"
          % (info["service"], info["repo"], d, "yes" if info["onboarded"] else "NO"))
    if not info["onboarded"]:
        print("\n!! not onboarded — ask the user whether to run waypoint-onboard before proceeding")
    print_guardrails(guardrails_for(d, [p.strip() for p in (a.paths or "").split(",") if p.strip()]),
                     "matching your paths" if a.paths else "")

    wy = d / "waypoint.yaml"
    if wy.exists():
        print("\n--- waypoint.yaml ---")
        print(wy.read_text().strip())
        cfm = commands_fm(read_fm(wy)[0])
        if cfm["verified_sha"]:
            cn, _ = doc_staleness(repo, cfm)
            if cn:
                print("!! the commands block is %d commit(s) behind its manifests — verify before "
                      "trusting the gate list (wp verify %s commands)" % (cn, info["service"]))

    docs = [(f, read_fm(f)[0]) for f in sorted(d.glob("*.md")) if f.name not in NON_DOC_FILES]
    if docs:
        print("\n--- docs (verified | commits to its paths since) ---")
        for f, fm in docs:
            if f.name == "known-context.md":
                snaps = snapshots(d)
                old = [s for s in snaps if s["age"] > SNAPSHOT_DAYS]
                extra = "exempt"
                if snaps:
                    extra += " (%d snapshot claim(s)%s)" % (
                        len(snaps), ", %d over %dd" % (len(old), SNAPSHOT_DAYS) if old else "")
                print("  %-18s %s  %s" % (f.name, fm.get("verified", "-"), extra))
                continue
            n, _ = doc_staleness(repo, fm)
            flag = "NO-ANCHOR (wp verify)" if n is None else ("ok" if n == 0 else "STALE:%d — check against source" % n)
            print("  %-18s %s  %s" % (f.name, fm.get("verified", "unverified"), flag))

    ex = explainer_index(d)
    if ex:
        print("\n--- explainers (update these; do not duplicate) ---")
        for slug, thesis in ex:
            print("  [[%s]] — %s" % (slug, thesis or "(no thesis line)"))

    plans = []
    for f in plan_files(d):
        fm, _ = read_fm(f)
        plans.append((f, fm.get("status", "?"), fm.get("title", f.stem)))
    if plans:
        print("\n--- plans ---")
        for f, st, title in plans:
            print("  %-9s %-28s %s" % (st, f.stem, title))

    led = ledger_recent(d)
    if led:
        print("\n--- ledger (last %d — never read the whole file) ---" % len(led))
        for h in led:
            print("  %s" % h)

    ideas = ideas_index(d)
    if ideas:
        print("\n--- ideas log (%d total — read in full before generating new ones; "
              "don't resurface a discarded idea without new evidence) ---" % len(ideas))
        for h in ideas:
            print("  %s" % h)

    if a.plan:
        f = find_plan(d, a.plan)
        pfm, _ = read_fm(f)
        held = dev_deploy_state(pfm, git_cwd_for(pfm, info))
        print("\n--- plan: %s ---" % f.name)
        print("path: %s" % f)
        if held:
            print("!! dev is currently held by this plan's branch (%s) — hand it back when you "
                  "stop, or say who owns it" % held)
        print(f.read_text().strip())


def find_plan(d: Path, ident: str):
    """Exact stem, then `<ident>-…` prefix, then substring — so FUSE-1056 never
    matches FUSE-10560 and a bare ticket resolves to its plan."""
    files = plan_files(d)
    il = ident.lower()
    exact = [f for f in files if f.stem.lower() == il]
    if exact:
        return exact[0]
    cands = [f for f in files if f.stem.lower().startswith(il + "-")]
    if not cands:
        cands = [f for f in files if il in f.stem.lower()]
    if not cands:
        die("no plan matching %r in %s/plans" % (ident, d))
    if len(cands) > 1:
        die("ambiguous plan %r: %s" % (ident, ", ".join(f.stem for f in cands)))
    return cands[0]


def find_by_ticket(ticket: str):
    """Every plan across the whole vault whose frontmatter `ticket:` matches, case-insensitive."""
    t = ticket.strip().lower()
    hits = []
    for name, s_dir in iter_services():
        for f in plan_files(s_dir):
            fm, _ = read_fm(f)
            if str(fm.get("ticket") or "").strip().lower() == t:
                hits.append((name, f, fm))
    return hits


def cmd_find(a):
    hits = find_by_ticket(a.ticket)
    if not hits:
        die("no plan tracks ticket %s" % a.ticket)
    for service, f, fm in hits:
        print("%s  service=%-16s status=%-9s updated=%-10s stem=%s\n    plan=%s"
              % (a.ticket, service, fm.get("status", "?"), plan_date(fm) or "?", f.stem, f))


def cmd_stale(a):
    info = resolve(a.service)
    d, repo = Path(info["vault"]), Path(info["repo"]) if info["repo"] else None
    fetch_origin(repo)
    any_stale = False
    rows = []
    emit = (lambda *x: None) if a.json else print
    for f in sorted(d.glob("*.md")):
        if f.name in NON_DOC_FILES:
            continue
        fm, _ = read_fm(f)
        if f.name == "known-context.md":
            emit("%-18s exempt (human knowledge does not rot on commits)" % f.name)
            continue
        n, lines = doc_staleness(repo, fm, limit=5)
        rows.append({"doc": f.name, "commits": n, "sha": str(fm.get("verified_sha") or ""),
                     "paths": [str(p) for p in (fm.get("verified_paths") or [])], "subjects": lines})
        if n is None:
            emit("%-18s no anchor — re-verify with: wp verify %s %s --paths ..."
                  % (f.name, info["service"], f.name))
            continue
        sha = str(fm.get("verified_sha") or "")
        if repo and anchor_ancestry(repo, sha, default_branch_ref(repo)) == "off-branch":
            emit("%-18s anchor %s is NOT on %s (pre-squash or rebased) — the count below is "
                  "meaningless; re-verify: wp verify %s %s --paths %s"
                  % (f.name, sha[:9], default_branch_ref(repo), info["service"], f.name,
                     ",".join(str(p) for p in (fm.get("verified_paths") or []))))
            any_stale = True
            continue
        emit("%-18s %d commit(s) since %s on %s"
              % (f.name, n, str(fm.get("verified_sha") or "?")[:9],
                 ", ".join(str(p) for p in (fm.get("verified_paths") or ["<repo>"]))))
        for l in lines:
            emit("    %s" % l)
        any_stale = any_stale or n > 0
    if a.json:
        print(json.dumps({"service": info["service"], "docs": rows,
                          "stale": any_stale}, indent=2, default=str))
        return
    if not any_stale:
        emit("\nno doc is behind its verified paths")
    else:
        sys.exit(3)


def cmd_verify_commands(a, info, d, repo):
    wy = d / "waypoint.yaml"
    data, body, err, raw = load_fm(wy)
    if data is None:
        die("%s does not parse (%s)" % (rel(wy), err))
    want = [p.strip() for p in (a.paths or "").split(",") if p.strip()]
    if not want:
        want = [str(p) for p in (data.get("commands_verified_paths") or [])]
    if not want:
        die("--paths is required: name the manifest files whose change would invalidate the "
            "commands block (package.json, mise.toml, pnpm-workspace.yaml, go.mod, ...)")
    bad = [w for w in want if not is_manifest(w)]
    if bad:
        die("a commands anchor may only name manifest files, not source: %s\n"
            "anchored to a source directory it fires on every commit and gets ignored" % ", ".join(bad))
    if not repo or not Path(repo).is_dir():
        die("no repo resolved for %s" % info["service"])
    fetch_origin(Path(repo))
    ref = default_branch_ref(Path(repo))
    missing = [w for w in want if sh(["git", "cat-file", "-e", "%s:%s" % (ref, w)], cwd=repo)[0] != 0]
    if missing:
        die("these paths do not exist at %s: %s" % (ref, ", ".join(missing)))
    rc, sha, _ = sh(["git", "rev-parse", "--short", ref], cwd=repo)
    txt = wy.read_text()
    for k, v in (("commands_verified", TODAY), ("commands_verified_sha", sha if rc == 0 else "unknown"),
                 ("commands_verified_paths", "[%s]" % ", ".join(want))):
        line = "%s: %s" % (k, v)
        txt = (re.sub(r"^%s:.*$" % k, line, txt, count=1, flags=re.M)
               if re.search(r"^%s:" % k, txt, re.M) else txt.rstrip() + "\n" + line + "\n")
    atomic_write(wy, txt)
    print("re-anchored %s commands block at %s (%s)" % (info["service"], sha, TODAY))


def cmd_verify(a):
    info = resolve(a.service)
    d, repo = Path(info["vault"]), info["repo"]
    if a.doc in ("commands", "waypoint.yaml"):
        return cmd_verify_commands(a, info, d, repo)
    f = d / a.doc
    if not f.exists():
        die("no such doc: %s" % f)
    if a.doc == "known-context.md" and a.paths:
        die("known-context.md is exempt from staleness anchors — do not stamp verified_paths on it")
    fm, body, err = read_fm_strict(f)
    if err:
        die("%s: frontmatter did not parse (%s) — fix by hand before writing" % (f, err))
    if a.doc == "known-context.md":
        fm["verified"] = TODAY
        write_fm(f, fm, body)
        print("known-context.md: stamped verified date only (exempt from sha anchors)")
        return
    if not repo or not Path(repo).is_dir():
        if a.paths:
            die("no repo resolved for %s — cannot validate --paths against a ref" % info["service"])
        warn("no repo resolved for %s — verified_sha left \"unknown\"" % info["service"])
        rc, sha = 1, "unknown"
    else:
        fetch_origin(repo)
        ref = default_branch_ref(Path(repo))
        rc, sha, _ = sh(["git", "rev-parse", "--short", ref], cwd=repo)
        if a.paths:
            want = [p.strip() for p in a.paths.split(",") if p.strip()]
            # Check against the ref just anchored to, not the local working tree — a
            # checkout behind origin (or on an unrelated branch) can genuinely be missing
            # a path that's real at the anchor commit.
            missing = [w for w in want if sh(["git", "cat-file", "-e", "%s:%s" % (ref, w)], cwd=repo)[0] != 0]
            if missing:
                die("these paths do not exist at %s in %s: %s\n"
                    "an anchor on a non-existent path never reports staleness — use real paths"
                    % (ref, repo, ", ".join(missing)))
            fm["verified_paths"] = want
    fm["verified"] = TODAY
    fm["verified_sha"] = sha if rc == 0 else "unknown"
    write_fm(f, fm, body)
    print("re-anchored %s at %s (%s)" % (f.name, fm["verified_sha"], TODAY))


def cmd_plan_new(a):
    info = resolve(a.service)
    d = Path(info["vault"])
    (d / "plans").mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", (a.title or "").lower()).strip("-")[:48]
    stem = "-".join(x for x in [a.ticket, slug] if x) or "untitled"
    f = d / "plans" / ("%s.md" % stem)
    if f.exists():
        die("plan already exists: %s" % f)
    repo = info["repo"] if info["repo"] and Path(info["repo"]).is_dir() else None

    base = a.base
    if not base:
        ref = default_branch_ref(Path(repo)) if repo else "HEAD"
        base = ref if ref != "HEAD" else "origin/master"

    branch = worktree = base_sha = "unknown"
    if a.config_only:
        branch = worktree = base_sha = "none"
    elif not a.no_git:
        cwd = Path.cwd()
        rc_top, top, _ = sh(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
        here = locate() if rc_top == 0 else {}
        if rc_top != 0:
            warn("cwd %s is not a git repo — branch/worktree left \"unknown\"; run from the service's "
                 "worktree, or edit the plan frontmatter" % cwd)
        elif repo and here.get("repo") != repo:
            warn("cwd %s is a checkout of %s, not %s — branch/worktree left \"unknown\"; run from the "
                 "service's worktree, or edit the plan frontmatter" % (cwd, here.get("repo"), repo))
        else:
            rc, b, _ = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
            branch = b if rc == 0 else "unknown"
            worktree = top
            rc3, bs, _ = sh(["git", "merge-base", base, "HEAD"], cwd=cwd)
            base_sha = bs[:9] if rc3 == 0 else "unknown"

    tpl = (TEMPLATES / "plan.md").read_text()
    m = FM.match(tpl)
    fm_text, body_text = (m.group(1), m.group(2)) if m else ("", tpl)
    vals = {"ticket": a.ticket or "none", "title": a.title or stem, "service": info["service"],
            "repo": repo or "unknown", "branch": branch, "worktree": worktree, "base": base,
            "base_sha": base_sha, "date": TODAY}

    def sub(text, quote):
        # Frontmatter values go in as JSON strings — a valid double-quoted YAML scalar, so a
        # title containing ": " or a leading "?" can't corrupt the block. Dates become strings.
        for k, v in vals.items():
            text = text.replace("{{%s}}" % k, json.dumps(str(v), ensure_ascii=False) if quote else str(v))
        return text

    # A plan promoted from a programme unit carries the linkage `wp fleet` renders as `· prog/unit`.
    extra = ""
    if getattr(a, "programme", None):
        extra += "programme: %s\n" % json.dumps(a.programme, ensure_ascii=False)
    if getattr(a, "unit", None):
        extra += "unit: %s\n" % json.dumps(a.unit, ensure_ascii=False)
    # Seed the implementation tier from the unit's ledger estimate; the plan is authoritative hereafter.
    if getattr(a, "programme", None) and getattr(a, "unit", None):
        tier = _unit_tier(a.programme, a.unit)
        if tier:
            model, effort = tier
            if model:
                extra += "impl_model: %s\n" % json.dumps(model, ensure_ascii=False)
            if effort:
                extra += "impl_effort: %s\n" % json.dumps(effort, ensure_ascii=False)
    atomic_write(f, "---\n%s\n%s---\n%s" % (sub(fm_text, True), extra, sub(body_text, False)))
    _, _, err = read_fm_strict(f)
    if err:
        f.unlink()
        die("generated plan frontmatter invalid (%s) — title: %r" % (err, a.title))
    print(f)


def cmd_plan_status(a):
    info = resolve(a.service)
    f = find_plan(Path(info["vault"]), a.plan)
    fm, body, err = read_fm_strict(f)
    if err:
        die("%s: frontmatter did not parse (%s) — fix by hand before writing" % (f, err))
    old = fm.get("status")
    reason = (getattr(a, "reason", None) or "").strip()
    if a.status in ("blocked", "abandoned") and not reason:
        die("--reason is required for --status %s. A blocked or abandoned plan whose reason "
            "lives only in someone's head is the one nobody can pick up." % a.status)
    fm["status"] = a.status
    fm["updated"] = TODAY
    if reason:
        fm["reason"] = reason
    elif "reason" in fm:
        del fm["reason"]
    if a.status == "blocked":
        fm.setdefault("blocked_since", TODAY)   # keep the original date across a re-block
    elif "blocked_since" in fm:
        del fm["blocked_since"]
    if a.pr:
        fm["pr"] = str(a.pr)
    if not write_fm(f, fm, body):
        return
    print("%s: %s -> %s" % (f.stem, old, a.status))
    if a.status != "abandoned":
        return
    # Abandoning leaves things behind that git does not own. This is derived from real state,
    # not a form to fill: a checklist you have to populate yourself is one nobody populates.
    wt = git_cwd_for(fm, resolve(a.service))
    items = []
    if not is_config_only(fm):
        on_dev = dev_deploy_state(fm, wt)
        if on_dev:
            items.append("dev is HELD by this branch (%s) — put it back, or say who owns it" % on_dev)
        pr, src, _ = plan_pr(fm, wt)
        if pr:
            pf = pr_facts(pr, wt)
            if not pf.get("merged") and pf.get("state") == "OPEN":
                items.append("PR #%s is still OPEN — close it, or say why it stays" % pr)
        rec_wt = str(fm.get("worktree") or "")
        if rec_wt and rec_wt.lower() not in ("none", "unknown") and Path(rec_wt).is_dir():
            items.append("worktree still on disk: %s — `git worktree remove` it" % rec_wt)
        if wt and fm.get("branch"):
            rc, counts, _ = sh(["git", "rev-list", "--left-right", "--count",
                                "%s...HEAD" % (fm.get("base") or "origin/master")], cwd=wt)
            if rc == 0 and "\t" in counts:
                ahead = counts.split("\t")[1].strip()
                if ahead not in ("", "0"):
                    items.append("branch %s is %s commit(s) ahead and unmerged" % (fm["branch"], ahead))
    roll = section(body, "Rollout & rollback") or ""
    shared = [l.strip() for l in roll.splitlines() if "shared state touched" in l.lower()]
    if shared:
        items.append("Rollout & rollback names shared state git does not own — re-read it: %s"
                     % _first_line(shared[0].lstrip("-* "), 80))
    print("\nabandoned. Before you walk away — derived from real state, nothing believed:")
    if not items:
        print("  nothing left behind that this can see (no dev hold, no open PR, no worktree, "
              "nothing ahead)")
    for i in items:
        print("  [ ] %s" % i)


def cmd_plan_set_model(a):
    # The recommended tier for *implementing* this plan, decided at plan time once the increments
    # are known. Free-form frontmatter, round-tripped like every other key; orient reads it and
    # `wp brief` surfaces it so waypoint-work can gate on it. Kept out of set-status deliberately:
    # the model recommendation is a property of the work, not a status transition.
    info = resolve(a.service)
    f = find_plan(Path(info["vault"]), a.plan)
    fm, body, err = read_fm_strict(f)
    if err:
        die("%s: frontmatter did not parse (%s) — fix by hand before writing" % (f, err))
    if not a.model and not a.effort:
        die("pass --model and/or --effort")
    if a.model:
        fm["impl_model"] = a.model
    if a.effort:
        fm["impl_effort"] = a.effort
    fm["updated"] = TODAY
    if not write_fm(f, fm, body):
        return
    print("%s: impl_model=%s impl_effort=%s" % (f.stem, fm.get("impl_model"), fm.get("impl_effort")))


# --- programmes --------------------------------------------------------------
# A programme is a multi-unit effort tracked by a `## Unit status` ledger in its Migration State
# doc. These commands are the programme-level counterpart to `plan new`/`tick`/`brief`: scaffold a
# programme, read the ledger (counts + next unblocked unit), and advance a unit's status. The
# ledger parse is deliberately tolerant — only a `Unit` cell and a `St` glyph are required — so the
# hand-authored ledgers that predate this tooling parse without a rewrite.

PROGRAMME_GLYPHS = {
    "⬜": "todo", "🟨": "doing", "✅": "done",
    "⛔": "blocked", "⏸": "deferred", "❌": "dropped", "🔄": "rescoped",
}
GLYPH_BY_STATE = {v: k for k, v in PROGRAMME_GLYPHS.items()}
STATE_ORDER = ["done", "doing", "todo", "blocked", "deferred", "dropped", "rescoped", "unknown"]


def find_programme(ident):
    """Resolve a programme by folder name or `programme:` slug (case/punctuation-loose) to
    (name, state_path). The migration-state-tagged doc is the ledger."""
    want = re.sub(r"[^a-z0-9]+", "", (ident or "").lower())
    by_folder = {}  # one entry per programme folder, preferring its migration-state (ledger) doc
    for name, path, fm, err in iter_programmes():
        norm = {re.sub(r"[^a-z0-9]+", "", k.lower())
                for k in (name, str(fm.get("programme") or ""), path.parent.name)}
        if not (want and any(want in k for k in norm if k)):
            continue
        tags = fm.get("tags") or []
        tags = [tags] if isinstance(tags, str) else tags
        is_ledger = any(str(t) == PROGRAMME_TAG or str(t).endswith("-state") for t in tags)
        cur = by_folder.get(path.parent)
        if cur is None or (is_ledger and not cur[2]):
            by_folder[path.parent] = (name, path, is_ledger)
    if not by_folder:
        have = ", ".join(sorted({n for n, _, _, _ in iter_programmes()})) or "none"
        die("no programme matching %r under %s (have: %s)" % (ident, PROGRAMMES, have))
    if len(by_folder) > 1:
        die("ambiguous programme %r: %s" % (ident, ", ".join(v[0] for v in by_folder.values())))
    name, path, _ = next(iter(by_folder.values()))
    return name, path


def _row_cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_table_sep(cells):
    real = [c for c in cells if c != ""]
    return bool(real) and all(re.fullmatch(r":?-{2,}:?", c) for c in real)


def parse_ledger(body):
    """Every unit row under `## Unit status`, tolerant of per-programme columns. Required per row:
    a `Unit` cell and a `St` glyph. Returns dicts with unit, glyph, state, group, deps[], pr,
    cols{header:idx}, st_col, and line (0-based index into body.split('\\n')) for in-place edits."""
    units, group, header, cols, in_sec, sec_level = [], None, None, {}, False, 0
    for i, raw in enumerate(body.split("\n")):
        s = raw.strip()
        h = re.match(r"^(#{2,6})\s*(.*)$", s)
        if h:
            level, title = len(h.group(1)), h.group(2).strip()
            if re.match(r"unit (status|ledger)\b", title, re.I):
                in_sec, sec_level, group, header = True, level, None, None
            elif in_sec and level <= sec_level:
                in_sec = False
            elif in_sec:
                group, header = (title or group), None
            continue
        if not in_sec or not s.startswith("|"):
            continue
        cells = _row_cells(raw)
        if _is_table_sep(cells):
            continue
        low = [c.lower() for c in cells]
        if header is None:
            if "unit" in low:
                header, cols = low, {name: idx for idx, name in enumerate(low)}
            continue

        def cell(names, default=""):
            for n in names:
                j = cols.get(n)
                if j is not None and j < len(cells):
                    return cells[j]
            return default

        unit = re.sub(r"[*`]", "", cell(["unit"])).strip()
        if not unit:
            continue
        st_col = cols.get("st", cols.get("status"))
        glyph = ""
        if st_col is not None and st_col < len(cells):
            glyph = next((g for g in PROGRAMME_GLYPHS if g in cells[st_col]), "")
        deps = [d.strip(" *`") for d in re.split(r"[,/]", cell(["deps", "dep", "prereq", "prereqs"]))
                if d.strip(" *`")]
        units.append({
            "unit": unit, "glyph": glyph, "state": PROGRAMME_GLYPHS.get(glyph, "unknown"),
            "group": group, "deps": deps, "pr": cell(["pr", "prs"]),
            "cols": dict(cols), "st_col": st_col, "line": i,
        })
    return units


def _counts(units):
    c = {}
    for u in units:
        c[u["state"]] = c.get(u["state"], 0) + 1
    return c


def _summary(counts):
    return " ".join("%s%d" % (GLYPH_BY_STATE.get(st, "?"), counts[st])
                    for st in STATE_ORDER if counts.get(st))


def next_units(units):
    """todo units whose every dependency that names a real unit is done. An unknown dep (an
    external ref) is treated as satisfied, not as a permanent wedge."""
    done = {u["unit"].lower() for u in units if u["state"] == "done"}
    known = {u["unit"].lower() for u in units}
    return [u for u in units if u["state"] == "todo"
            and all(d.lower() in done or d.lower() not in known for d in u["deps"])]


def _edit_cell(row, idx, value):
    """Replace the idx-th pipe-delimited cell (0-based) of a table row by position, leaving every
    other cell — including a later Notes cell that itself contains `|` — byte-for-byte untouched."""
    parts = row.split("|")
    target = idx + 1  # parts[0] is the text before the first pipe
    if target < len(parts):
        parts[target] = " %s " % str(value).strip()
    return "|".join(parts)


def _render_programme_doc(vals, services, tpl_name):
    tpl = (TEMPLATES / tpl_name).read_text()
    m = FM.match(tpl)
    fm_text, body_text = (m.group(1), m.group(2)) if m else ("", tpl)

    def sub(text, quote):
        text = text.replace("{{services}}", json.dumps(services))
        for k, v in vals.items():
            text = text.replace("{{%s}}" % k, json.dumps(str(v), ensure_ascii=False) if quote else str(v))
        return text

    return "---\n%s\n---\n%s" % (sub(fm_text, True), sub(body_text, False))


def cmd_programme_new(a):
    name = a.name.strip()
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    d = PROGRAMMES / name
    if d.exists():
        die("programme folder already exists: %s" % d)
    services = a.service or []
    d.mkdir(parents=True)
    for tpl, out, suffix in (("programme-overview.md", "Overview.md", "Overview"),
                             ("programme.md", "Migration State.md", "Migration State")):
        f = d / out
        vals = {"name": name, "title": "%s — %s" % (name, suffix), "slug": slug,
                "owner": a.owner or "", "date": TODAY}
        atomic_write(f, _render_programme_doc(vals, services, tpl))
        _, _, err = read_fm_strict(f)
        if err:
            die("generated %s frontmatter invalid (%s)" % (out, err))
    print(d)


def cmd_programme_status(a):
    name, path = find_programme(a.name)
    _, body = read_fm(path)
    units = parse_ledger(body)
    if not units:
        die("no `## Unit status` ledger found in %s" % path)
    print("%s — %d units · %s" % (name, len(units), _summary(_counts(units))))
    groups = {}
    for u in units:
        groups.setdefault(u["group"] or "(ungrouped)", []).append(u)
    for g, us in groups.items():
        c = _counts(us)
        print("  %-34s %2d/%-3d %s" % (g[:34], c.get("done", 0), len(us), _summary(c)))
    nxt = next_units(units)
    print("  next: %s" % (", ".join(u["unit"] for u in nxt[:4]) if nxt else "— nothing unblocked"))


def cmd_programme_next(a):
    name, path = find_programme(a.name)
    _, body = read_fm(path)
    units = parse_ledger(body)
    if not units:
        die("no `## Unit status` ledger found in %s" % path)
    nxt = next_units(units)
    if not nxt:
        blocked = sum(1 for u in units if u["state"] == "blocked")
        print("%s: nothing unblocked%s" % (name, (" (%d blocked)" % blocked) if blocked else ""))
        return
    for u in nxt[:6]:
        grp = (" [%s]" % u["group"]) if u["group"] else ""
        dep = (" · deps %s" % ", ".join(u["deps"])) if u["deps"] else ""
        print("%s%s%s" % (u["unit"], grp, dep))


def cmd_programme_tick(a):
    name, path = find_programme(a.name)
    fm, body, err = read_fm_strict(path)
    if err:
        die("%s: frontmatter did not parse (%s) — fix by hand" % (path, err))
    glyph = GLYPH_BY_STATE[a.status]
    units = parse_ledger(body)
    target = next((u for u in units if u["unit"].lower() == a.unit.lower()), None)
    if not target:
        die("no unit %r in %s (have: %s)" % (a.unit, name, ", ".join(u["unit"] for u in units)))
    lines = body.split("\n")
    row = lines[target["line"]]
    if target["st_col"] is not None:
        row = _edit_cell(row, target["st_col"], glyph)
    if a.pr is not None:
        pr_col = target["cols"].get("pr", target["cols"].get("prs"))
        if pr_col is None:
            warn("no PR column in this ledger — recorded status only")
        else:
            row = _edit_cell(row, pr_col, a.pr)
    lines[target["line"]] = row
    fm["updated"] = TODAY
    if not write_fm(path, fm, "\n".join(lines)):
        return
    record_work_usage("programme_tick", programme=name, unit=target["unit"], status=a.status)
    print("%s: %s -> %s%s" % (a.unit, target["glyph"] or "·", glyph, (" pr=%s" % a.pr) if a.pr else ""))


def _unit_tier(programme_ident, unit_id):
    """(model, effort) recommended implementation tier for a programme unit, from its ledger `Tier`
    cell, or None. Best-effort — a promotion seed for `plan new`, never a reason to fail: any
    resolution miss (no programme, no unit, no Tier column, empty cell) returns None quietly."""
    try:
        _, path = find_programme(programme_ident)
        _, body = read_fm(path)
        units = parse_ledger(body)
        u = next((x for x in units if x["unit"].lower() == unit_id.lower()), None)
        if not u:
            return None
        tier_col = u["cols"].get("tier")
        if tier_col is None:
            return None
        cells = _row_cells(body.split("\n")[u["line"]])
        cur = cells[tier_col] if tier_col < len(cells) else ""
        model, _, effort = cur.partition("/")
        model, effort = model.strip(), effort.strip()
        return (model, effort) if (model or effort) else None
    except (SystemExit, Exception):
        return None


def cmd_programme_set_model(a):
    # A unit's recommended IMPLEMENTATION tier — a `<model>/<effort>` estimate in the ledger's `Tier`
    # column, the programme-level counterpart to `plan set-model`. A unit is a ledger row, not
    # frontmatter, so this edits the Tier cell in place. It seeds the plan's `impl_model`/`impl_effort`
    # when the unit is promoted (`plan new --programme … --unit …`); the plan is authoritative once it
    # exists. Kept out of `tick` deliberately: the recommendation is a property of the work, not a
    # status transition.
    name, path = find_programme(a.name)
    fm, body, err = read_fm_strict(path)
    if err:
        die("%s: frontmatter did not parse (%s) — fix by hand" % (path, err))
    if not a.model and not a.effort:
        die("pass --model and/or --effort")
    units = parse_ledger(body)
    target = next((u for u in units if u["unit"].lower() == a.unit.lower()), None)
    if not target:
        die("no unit %r in %s (have: %s)" % (a.unit, name, ", ".join(u["unit"] for u in units)))
    tier_col = target["cols"].get("tier")
    if tier_col is None:
        die("no `Tier` column in this ledger — add one to the `## Unit status` table first")
    lines = body.split("\n")
    row = lines[target["line"]]
    cells = _row_cells(row)
    cur = cells[tier_col] if tier_col < len(cells) else ""
    model, _, effort = cur.partition("/")
    model = (a.model or model).strip()
    effort = (a.effort or effort).strip()
    value = "/".join(x for x in (model, effort) if x)
    lines[target["line"]] = _edit_cell(row, tier_col, value)
    fm["updated"] = TODAY
    if not write_fm(path, fm, "\n".join(lines)):
        return
    print("%s: tier=%s" % (a.unit, value or "—"))


def _prepend_entry(path: Path, head: str, entry: str, force: bool, label: str):
    text = path.read_text()
    _remember(path)
    newest = next((l for l in text.splitlines() if l.startswith("## ")), None)
    if newest is not None and newest.strip() == head.strip() and not force:
        print("%s: newest entry already is %r — not appended (pass --force to append anyway)" % (label, head))
        return False
    parts = text.split("\n## ", 1)
    if len(parts) == 2:
        atomic_write(path, "%s\n\n%s\n## %s" % (parts[0].rstrip(), entry, parts[1]))
    else:
        atomic_write(path, "%s\n\n%s" % (text.rstrip(), entry))
    return True


def cmd_ledger(a):
    info = resolve(a.service)
    d = Path(info["vault"])
    led = d / "ledger.md"
    if not led.exists():
        cmd_init(argparse.Namespace(service=info["service"]))
    programme = find_programme(a.programme)[0] if a.programme else None
    body = a.body if a.body else sys.stdin.read()
    head = "## %s — %s" % (a.date or TODAY, a.ticket or (a.title or "work"))
    entry = "%s\n\n%s\n\n%s\n" % (head, (a.title or "").strip(), body.strip())
    if _prepend_entry(led, head, entry, a.force, rel(led)):
        record_work_usage("ledger", service=info["service"], ticket=a.ticket, programme=programme,
                          heading=head, prs=sorted(set(PR_REF.findall(body))))
        print("appended to %s: %s" % (led, head))


def cmd_idea(a):
    info = resolve(a.service)
    d = Path(info["vault"])
    d.mkdir(parents=True, exist_ok=True)
    f = d / "ideas-log.md"
    if not f.exists():
        atomic_write(
            f,
            "---\ntags: [waypoint, ideas]\n---\n# %s — ideas log\n\n"
            "Every idea waypoint-ideate has surfaced, kept or discarded, newest first.\n"
            "Read in full before generating new ideas — don't resurface a discarded idea\n"
            "without new evidence that changed the picture.\n\n" % info["service"]
        )
    head = "## %s — %s — %s" % (TODAY, a.status, a.title)
    meta = ["source: %s" % a.source]
    if a.plan:
        meta.append("plan: %s" % a.plan)
    entry = "%s\n%s\n\n%s\n" % (head, "\n".join(meta), a.reason.strip())
    if _prepend_entry(f, head, entry, a.force, rel(f)):
        print("logged to %s: %s" % (f, head))


def plan_facts(fm, body, wt, base=None, net=True, vault_dir=None, plan_path=None):
    """Every fact sign-off and re-entry both need, gathered once and printed by neither.
    `gate()` turns these into blockers; `cmd_signoff` and `cmd_brief` are two renderings of it.
    Collection was previously inlined in sign-off, so the only way to learn whether a PR was red
    or dev was still held was to finish the work and run the gate."""
    config_only = is_config_only(fm)
    base = base or str(fm.get("base") or "origin/master")
    branch = str(fm.get("branch") or "")
    f = {"plan_path": str(plan_path) if plan_path else None,
         "config_only": config_only, "wt": wt, "base": base, "branch": branch,
         "status": fm.get("status"), "ticket": fm.get("ticket"), "title": fm.get("title"),
         "updated": fm.get("updated"), "pr_recorded": fm.get("pr"),
         "reason": fm.get("reason"), "blocked_since": fm.get("blocked_since"),
         "diff": None, "ahead": None, "behind": None, "head": None, "dirty": [],
         "missing_worktree": None}

    rec_wt = str(fm.get("worktree") or "")
    if rec_wt and rec_wt.lower() not in ("none", "unknown") and not Path(rec_wt).is_dir():
        f["missing_worktree"] = rec_wt

    if not config_only and wt:
        rc, stat, _ = sh(["git", "diff", "--stat", "%s...HEAD" % base], cwd=wt)
        rc2, files, _ = sh(["git", "diff", "--name-only", "%s...HEAD" % base], cwd=wt)
        f["diff"] = {"stat": stat if rc == 0 and stat else "", "changed": files.splitlines() if rc2 == 0 else []}
        rc3, dirty, _ = sh(["git", "status", "--porcelain"], cwd=wt)
        if rc3 == 0 and dirty.strip():
            f["dirty"] = dirty.splitlines()
        rc4, counts, _ = sh(["git", "rev-list", "--left-right", "--count", "%s...HEAD" % base], cwd=wt)
        if rc4 == 0 and "\t" in counts:
            b, a_ = counts.split("\t")[:2]
            # left is base-only, right is HEAD-only: behind, then ahead. Labelling these the wrong
            # way round once is enough to make the whole brief untrustworthy.
            f["behind"], f["ahead"] = b.strip(), a_.strip()
        rc5, head, _ = sh(["git", "rev-parse", "--short", "HEAD"], cwd=wt)
        f["head"] = head if rc5 == 0 else None

    inc = section(body, "Increments")
    f["inc_section"] = inc
    # Template guidance ships an illustrative `- [ ] 6. ...` gate example inside the section's own
    # HTML comment (so a fresh plan can see the syntax) — strip comments before scanning for real
    # checkboxes, or that example is counted as a genuine unchecked increment forever.
    inc_clean = strip_comments(inc) if inc is not None else None
    f["inc_unchecked"] = unchecked(inc_clean) if inc_clean is not None else []
    f["inc_ticked"] = len([l for l in (inc_clean or "").splitlines() if TICKED_RE.match(l)])
    ac = section(body, "Acceptance criteria")
    f["ac_section"] = ac
    ac_clean = strip_comments(ac) if ac is not None else None
    f["ac_unmet"] = unchecked(ac_clean) if ac_clean is not None else []
    f["ac_met"] = len([l for l in (ac_clean or "").splitlines() if TICKED_RE.match(l)])
    f["other_unchecked"] = len(unchecked(strip_comments(body))) - len(unchecked(inc_clean or "")) - len(unchecked(ac_clean or ""))
    f["placeholders"] = find_placeholders(body)

    ver = section(body, "Verification")
    ev = section(body, "Evidence") if ver is not None else None
    f["evidence_section"] = ev is not None
    # A plan written from the current template gates strictly on a dated bullet under
    # ### Evidence. One written before it has no such section, so it keeps the old
    # substantive-length check — six of the eight plans in the vault would otherwise flip to
    # BLOCKED overnight, two of them carrying thousands of characters of real evidence.
    if ev is not None:
        f["evidence_dated"] = [l.strip() for l in ev.splitlines()
                               if re.match(r"^\s*[-*]\s*(?:\*\*)?\d{4}-\d{2}-\d{2}", l)]
        f["verification_thin"] = not f["evidence_dated"]
    else:
        f["evidence_dated"] = []
        f["verification_thin"] = ver is None or len(strip_placeholders(ver)) < 40
    f["verification_undated"] = ver is not None and not re.search(r"\d{4}-\d{2}-\d{2}", ver)

    f["increments"] = parse_increments(inc_clean or "")
    f["gates_unmet"] = [i for i in f["increments"] if i["gate"] and not i["confirmed"]]
    f["gates_breached"] = [i for i in f["increments"] if i["ticked"] and i["gate"] and not i["confirmed"]]

    ac_lines = [l for l in (ac_clean or "").splitlines() if re.match(r"^\s*[-*] \[[ xX]\]", l)]
    cited = set()
    for i in f["increments"]:
        for m in re.finditer(r"\(AC ([\d,\s]+)\)", i["text"]):
            cited.update(x.strip() for x in m.group(1).split(",") if x.strip())
    f["ac_total_lines"] = len(ac_lines)
    f["ac_uncited"] = ([str(x) for x in range(1, len(ac_lines) + 1) if str(x) not in cited]
                       if cited else [])

    learn = section(body, "Learnings")
    f["learnings"] = None
    if learn is not None:
        lt = strip_placeholders(learn)
        if lt and lt.strip().strip("().").lower() != "none":
            f["learnings"] = lt

    f["programme"] = fm.get("programme")
    f["unit"] = fm.get("unit")
    f["unresolved"] = [l.strip() for l in body.splitlines() if l.strip().startswith("UNRESOLVED:")]

    # The written handback carries only what cannot be derived. When there isn't one, the
    # fallback is free and always true, so this block is never blank.
    hb = section(body, "Handback")
    f["handback"] = None
    if hb:
        m = re.search(r"^### (.+?)$(.*?)(?=^### |\Z)", strip_comments(hb), re.S | re.M)
        if m:
            f["handback"] = {"when": m.group(1).strip(),
                             "lines": [l.strip(" -") for l in m.group(2).strip().splitlines() if l.strip()]}
    f["since_last"] = []
    if not f["handback"] and wt and not config_only:
        rc, out, _ = sh(["git", "log", "--oneline", "-3", "%s..HEAD" % base], cwd=wt)
        if rc == 0 and out:
            f["since_last"] = out.splitlines()

    # An increment that has been "next" since this morning is what a six-instance day actually
    # produces, and nothing surfaced it. Plan mtime is the honest proxy: it moves on every tick,
    # decision and handback, so a long gap with work outstanding means no progress was recorded.
    f["idle_hours"] = None
    if f.get("plan_path"):
        try:
            age = dt.datetime.now() - dt.datetime.fromtimestamp(Path(f["plan_path"]).stat().st_mtime)
            f["idle_hours"] = age.total_seconds() / 3600.0
        except OSError:
            pass

    f["rows"], f["nosha"], f["unreachable"] = [], 0, []
    if not config_only and wt and inc is not None:
        for line in inc.splitlines():
            m = TICKED_RE.match(line)
            if not m:
                continue
            num = m.group(1) or "?"
            shas = [s for s in DONE_RE.findall(m.group(2))
                    if sh(["git", "rev-parse", "--verify", "--quiet", s + "^{commit}"], cwd=wt)[0] == 0]
            if not shas:
                f["nosha"] += 1
                f["rows"].append((num, "(none)", "-", "-"))
                continue
            for sha in shas:
                in_base = sh(["git", "merge-base", "--is-ancestor", sha, base], cwd=wt)[0] == 0
                # A squash merge leaves the shipped sha on base, never on the branch HEAD.
                reach = in_base or sh(["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=wt)[0] == 0
                f["rows"].append((num, sha, "yes" if reach else "NO",
                                  "-" if not reach else ("no" if in_base else "yes")))
                if not reach:
                    f["unreachable"].append((num, sha))

    f["touched_guardrails"] = []
    if vault_dir is not None:
        f["touched_guardrails"] = guardrails_for(vault_dir, (f["diff"] or {}).get("changed") or [])

    f["pr"] = f["pr_src"] = f["pr_disc"] = f["pf"] = None
    f["dev_hold"] = None
    if net:
        pr, src, disc = plan_pr(fm, wt)
        f["pr"], f["pr_src"], f["pr_disc"] = pr, src, disc
        if pr:
            f["pf"] = pr_facts(pr, wt)
        if not config_only:
            f["dev_hold"] = dev_deploy_state(fm, wt)
    return f


def gate(f):
    """Blockers stop a sign-off; notes are said out loud and don't. Pure — no i/o, no git."""
    blockers, notes = [], []
    if f["missing_worktree"]:
        notes.append("recorded worktree %s is missing — using %s" % (f["missing_worktree"], f["wt"]))
    if not f["config_only"]:
        if not f["wt"]:
            blockers.append("no worktree or repo directory to diff in — pass --worktree")
        else:
            if not (f["diff"] or {}).get("changed"):
                if (f.get("pf") or {}).get("merged"):
                    notes.append("no diff against %s: the PR is merged (squash), so the work is already on base" % f["base"])
                else:
                    blockers.append("no diff found against %s — nothing to sign off, or wrong base/worktree "
                                    "(a config-only plan should carry branch: none)" % f["base"])
            if f["dirty"]:
                blockers.append("uncommitted changes in %s (%d path(s))" % (f["wt"], len(f["dirty"])))
    if f["inc_section"] is None:
        blockers.append("plan has no ## Increments section")
    elif f["inc_unchecked"]:
        blockers.append("%d unchecked increment(s)" % len(f["inc_unchecked"]))
    if f["ac_unmet"]:
        blockers.append("%d unmet acceptance criteria" % len(f["ac_unmet"]))
    if f["other_unchecked"] > 0:
        notes.append("%d unchecked box(es) outside Increments/Acceptance criteria (not gating)" % f["other_unchecked"])
    if f["placeholders"]:
        blockers.append("plan still has %d unfilled template placeholder(s)" % len(f["placeholders"]))
    if f["verification_thin"]:
        blockers.append("plan has no dated evidence under ### Evidence — run waypoint-test"
                        if f["evidence_section"] else
                        "plan has no substantive Verification section — run waypoint-test")
    elif f["verification_undated"]:
        notes.append("Verification carries no date — evidence that can't be placed in time is hard "
                     "to re-run; date each bullet")
    for i in f["gates_breached"]:
        blockers.append("increment %s is ticked but its gate is unconfirmed: %s"
                        % (i["id"], i["gate"][:90]))
    if f["ac_uncited"]:
        notes.append("acceptance criteria %s are cited by no increment (add `(AC n)` to the "
                     "increment that discharges each, or say why it is out of scope)"
                     % ", ".join(f["ac_uncited"]))
    if f["learnings"]:
        notes.append("plan has unpromoted Learnings — read and promote into a durable doc before finishing")
    merged = bool((f.get("pf") or {}).get("merged"))
    for num, sha in f["unreachable"]:
        if merged:
            notes.append("increment %s: done sha %s is not on HEAD or base; the PR is merged, so it was "
                         "squashed or rebuilt" % (num, sha))
        else:
            blockers.append("increment %s: done sha %s is not an ancestor of HEAD in %s" % (num, sha, f["wt"]))
    if f["nosha"]:
        notes.append("%d ticked increment(s) without a commit sha (append `— done: <sha>` when ticking)" % f["nosha"])
    if f["pr_src"] == "error":
        notes.append("could not discover a PR for branch %s: %s" % (f["branch"], (f["pr_disc"] or {}).get("error")))
    pf = f["pf"]
    if f["pr"] and pf:
        if pf.get("error"):
            notes.append("could not read PR #%s: %s" % (f["pr"], pf["error"]))
        else:
            if pf.get("failing_checks"):
                blockers.append("failing checks: %s" % ", ".join(pf["failing_checks"][:6]))
            if pf.get("pending_checks"):
                notes.append("checks still running: %s" % ", ".join(pf["pending_checks"][:6]))
            if pf.get("unresolved_threads"):
                blockers.append("%d unresolved review thread(s)" % pf["unresolved_threads"])
            if pf.get("review") == "CHANGES_REQUESTED":
                blockers.append("review decision is CHANGES_REQUESTED")
            if not pf.get("merged"):
                notes.append("PR #%s is not merged (%s) — sign-off before merge is allowed; say so plainly"
                             % (f["pr"], pf.get("state")))
    elif not f["pr"]:
        notes.append("no PR expected (config-only)" if f["config_only"] else "no PR recorded on the plan")
    if f["touched_guardrails"]:
        notes.append("this diff touches %d guardrail(s) — listed above; confirm none is breached"
                     % len(f["touched_guardrails"]))
    if f["dev_hold"]:
        notes.append("dev may still be on this plan's branch (%s) — the last successful "
                     "manual-deploy was this branch. Put it back (`gh workflow run "
                     "manual-deploy.yaml --ref master`) and say so in #bifrost-general, or "
                     "state plainly that it is deliberately left there" % f["dev_hold"])
    return blockers, notes


W = 78


def _first_line(s, limit=200):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:limit]


def _inc_text(s):
    """The increment's own words: no checkbox, no number, no markdown emphasis."""
    s = re.sub(r"^\s*[-*]\s*\[[ xX]\]\s*", "", str(s or ""))
    s = re.sub(r"^\s*([A-Za-z]*\d+[a-z]?)\.\s*", "", s)
    return _first_line(s.replace("**", "").replace("`", ""), 400)


def whose_turn(f):
    """Deliberately dumb, and printed next to its verdict so a miscall is visibly wrong rather
    than quietly believed."""
    pf = f["pf"] or {}
    pr = f["pr"]
    hb = f.get("handback") or {}
    stated = next((l.split(":", 1)[1].strip() for l in hb.get("lines", [])
                   if l.lower().startswith("**turn:**") or l.lower().startswith("turn:")), None)
    if pr and pf.get("merged") and f["status"] in OPEN_STATUSES:
        return "YOUR TURN", "#%s is merged and the plan is still %s — it is owed a sign-off." % (pr, f["status"])
    if pf.get("failing_checks"):
        return "YOUR TURN", "#%s is red (%s). A red check on your PR is yours to clear." % (
            pr, ", ".join(c.split(" / ")[0] for c in pf["failing_checks"][:2]))
    if pf.get("review") == "CHANGES_REQUESTED":
        return "YOUR TURN", "#%s has changes requested." % pr
    if pf.get("unresolved_threads"):
        return "YOUR TURN", "%d unresolved review thread(s) on #%s." % (pf["unresolved_threads"], pr)
    if f["status"] == "blocked":
        return "WAITING ON THE WORLD", _first_line(f["reason"]) or "plan is marked blocked."
    if pr and pf.get("review") == "APPROVED" and not pf.get("merged") and not pf.get("draft"):
        # approved and green is not the reviewer's turn any more — it is waiting on you to merge
        return "YOUR TURN", "#%s is approved and green — merge it." % pr
    if f["inc_unchecked"]:
        return "AN AGENT'S TURN", "%d increment(s) left; nothing is blocking them." % len(f["inc_unchecked"])
    if pr and not pf.get("merged") and not pf.get("draft") and pf.get("state") == "OPEN":
        return "WAITING ON A REVIEWER", "#%s is open, green and has no decision yet." % pr
    if not f["ac_unmet"] and f["status"] in OPEN_STATUSES:
        return "YOUR TURN", "everything is ticked — run `wp signoff` to close it out."
    if stated:
        return {"me": "YOUR TURN", "agent": "AN AGENT'S TURN", "reviewer": "WAITING ON A REVIEWER",
                "world": "WAITING ON THE WORLD"}.get(stated.strip("* ").lower(), "YOUR TURN"), \
               "last handback said so."
    return None, None


def render_brief(f, stem):
    """One screen, hard-capped. Every number is derived and labelled with its direction: a brief
    that reports `7 behind` when the truth is `7 ahead` is never trusted again."""
    out = []
    unit = (" · %s/%s" % (f["programme"], f["unit"])) if f.get("programme") and f.get("unit") else ""
    head = " %s · %s · %s%s " % (f["ticket"] or stem, f["service"], f["status"] or "?", unit)
    clock = dt.datetime.now().strftime("%H:%M")
    out.append("───%s%s %s ───" % (head, "─" * max(1, W - len(head) - len(clock) - 8), clock))
    ac_total = f["ac_met"] + len(f["ac_unmet"])
    ac = "%d/%d acceptance criteria" % (f["ac_met"], ac_total) if ac_total else "NO acceptance criteria"
    out.append(" %d/%d increments · %s · plan updated %s" % (
        f["inc_ticked"], f["inc_ticked"] + len(f["inc_unchecked"]), ac, f["updated"] or "?"))
    mm, me = f.get("impl_model"), f.get("impl_effort")
    if mm or me:
        desc = " · ".join(x for x in [mm, ("%s effort" % me) if me else None] if x)
        out.append(" MODEL  %s recommended for implementation" % desc)
    out.append("")

    nxt = f["inc_unchecked"]
    if nxt:
        for i, (label, text) in enumerate((("NEXT", nxt[0]),) + ((("THEN", nxt[1]),) if len(nxt) > 1 else ())):
            gate = next((i["gate"] for i in f["increments"]
                         if _inc_text(i["line"]) == _inc_text(text) and i["gate"] and not i["confirmed"]), None)
            wrapped = textwrap.wrap(_inc_text(text), W - 8) or [""]
            keep = wrapped[:2] if i == 0 else wrapped[:1]
            if len(wrapped) > len(keep):
                keep[-1] = keep[-1] + " …"
            out.append(" %-6s %s" % (label, keep[0]))
            for extra in keep[1:]:
                out.append(" %-6s %s" % ("", extra))
            if gate:
                out.append(" %-6s GATE NOT MET — %s" % ("", _first_line(gate, W - 25)))
        if len(nxt) > 2:
            out.append(" %-6s ... %d more increment(s)" % ("", len(nxt) - 2))
        if f.get("idle_hours") and f["idle_hours"] >= 4:
            out.append(" %-6s no progress recorded for %s — stuck, or unwritten?"
                       % ("", "%dh" % f["idle_hours"] if f["idle_hours"] < 48 else "%dd" % (f["idle_hours"] / 24)))
    else:
        out.append(" NEXT   no unticked increments")
    out.append("")

    if f["config_only"]:
        out.append(" BRANCH config-only plan (no code diff expected)")
    elif f["branch"]:
        out.append(" BRANCH %s%s" % (f["branch"], (" @" + f["head"]) if f["head"] else ""))
        bits = []
        if f["ahead"] is not None:
            bits.append("%s ahead of %s, %s behind" % (f["ahead"], f["base"], f["behind"]))
        if f["dirty"]:
            bits.append("%d uncommitted (%s)" % (
                len(f["dirty"]), ", ".join(l.split(None, 1)[-1] for l in f["dirty"][:2]) + (", …" if len(f["dirty"]) > 2 else "")))
        if bits:
            out.append(" %-6s %s" % ("", " · ".join(bits)))

    pf = f["pf"] or {}
    if f["pr"]:
        state = "DRAFT" if pf.get("draft") else (pf.get("state") or "?")
        note = "merged" if pf.get("merged") else (pf.get("review") or "no review yet").replace("_", " ").lower()
        out.append(" PR     #%s %s · %s" % (f["pr"], state, note))
        if pf.get("failing_checks"):
            fc = ", ".join(c.split(" / ")[0] for c in pf["failing_checks"][:3])
            more = len(pf["failing_checks"]) - 3
            out.append(" %-6s FAILING: %s%s" % ("", fc[:W - 20], (" +%d more" % more) if more > 0 else ""))
        if pf.get("unresolved_threads"):
            out.append(" %-6s %d unresolved thread(s): %s" % (
                "", pf["unresolved_threads"], _first_line((pf.get("unresolved_sample") or [""])[0], 46)))
    elif not f["config_only"]:
        out.append(" PR     none recorded or discoverable")

    if not f["config_only"]:
        out.append(" DEV    %s" % ("HELD by this branch — hand it back when you stop" if f["dev_hold"]
                                   else "not held by this branch"))
    if f["unresolved"]:
        out.append(" OPEN   %s" % _first_line(f["unresolved"][0], W - 9))
        if len(f["unresolved"]) > 1:
            out.append(" %-6s ... %d more UNRESOLVED" % ("", len(f["unresolved"]) - 1))

    if f.get("handback"):
        out.append("")
        out.append(" LAST   %s" % _first_line(f["handback"]["when"], 20))
        for line in f["handback"]["lines"][:3]:
            out.append(" %-6s %s" % ("", _first_line(line, W - 9)))
    elif f.get("since_last"):
        out.append("")
        out.append(" SINCE  no handback written; commits since %s:" % f["base"])
        for line in f["since_last"][:3]:
            out.append(" %-6s %s" % ("", _first_line(line, W - 9)))

    turn, why = whose_turn(f)
    if turn:
        out.append("")
        for i, line in enumerate(textwrap.wrap("%s — %s" % (turn, why), W - 2)[:2]):
            out.append(" %s" % line)

    out = [l if len(l) <= W else l[:W - 2] + " …" for l in out]
    if len(out) > 28:                      # hard cap, whatever the plan's size
        out = out[:27] + [" ... trimmed; run `wp signoff` or open the plan for the rest"]
    out.append("─" * W)
    return "\n".join(out)


def _brief_target(a):
    """Zero-arg is the primary form: resolve the service from cwd, then the plan from the worktree
    you are standing in. Six windows, six lookups avoided."""
    info = resolve(a.service) if getattr(a, "service", None) else locate(None)
    if not info.get("vault") or not Path(info["vault"]).is_dir():
        die("no vault folder for %s — run waypoint-onboard, or pass a service name" % info.get("service"))
    d = Path(info["vault"])
    if getattr(a, "plan", None):
        return info, d, find_plan(d, a.plan)
    plans = []
    for p in plan_files(d):
        fm, _ = read_fm(p)
        if fm.get("status") in OPEN_STATUSES:
            plans.append((p, fm))
    if not plans:
        die("no open plan for %s — nothing to brief" % info["service"])
    rc, top, _ = sh(["git", "rev-parse", "--show-toplevel"], cwd=Path.cwd())
    if rc == 0 and top:
        here = [p for p, fm in plans if str(fm.get("worktree") or "").rstrip("/") == top.rstrip("/")]
        if len(here) == 1:
            return info, d, here[0]
    if len(plans) == 1:
        return info, d, plans[0][0]
    die("%d open plans for %s and cwd matches none of their worktrees — pass --plan:\n  %s"
        % (len(plans), info["service"], "\n  ".join(p.stem for p, _ in plans)))


def cmd_brief(a):
    info, d, f = _brief_target(a)
    fm, body = read_fm(f)
    wt = getattr(a, "worktree", None) or git_cwd_for(fm, info)
    facts = plan_facts(fm, body, wt, net=not a.no_net, vault_dir=d, plan_path=f)
    facts["service"] = info["service"]
    facts["impl_model"] = fm.get("impl_model")
    facts["impl_effort"] = fm.get("impl_effort")
    if a.json:
        facts.pop("inc_section", None); facts.pop("ac_section", None)
        print(json.dumps(facts, indent=2, default=str))
        return
    print(render_brief(facts, f.stem))


ADDABLE = {
    "rollout": ("## Rollout & rollback", """<!-- Added on demand. Written at plan time; amend in place as it changes.
     `Shared state touched:` is the single home for the five classes git does not own — a dev
     deploy, a prod config write, a Datadog monitor, a CI var or secret, cross-repo IaC. Reverting
     the branch undoes none of them, so if they are not written here they are not written down. -->

- **Order:** <what must ship before what, and what breaks if reversed>
- **Flags/config:** <flag or config key, old value -> new, and where it lives>
- **One-way doors:** <what cannot be undone once it is in prod, and the gate before it>
- **Rollback:** <per increment: git revert / forward-only / a flag flip>
- **Shared state touched:** <dev deploys, prod config writes, Datadog monitors, CI vars/secrets,
  cross-repo IaC — or "(none)", which is a deliberate claim>
- **Proof in prod:** <the metric or log line that shows this working, and its pre-deploy baseline>
"""),
    "options": ("## Options considered", """<!-- Added on demand. Why this approach and not the others — the thing the planning agent is
     asked for and the plan has otherwise had nowhere to put. Promote to a durable record with
     `wp decide --record` when it is worth defending in a review six months out. -->

- **Chosen — <approach>** — <why>
- **Rejected — <approach>** — <why not>
"""),
}


def cmd_add_section(a):
    info = resolve(a.service)
    f = find_plan(Path(info["vault"]), a.plan)
    fm, body, err = read_fm_strict(f)
    if err:
        die("%s: frontmatter did not parse (%s) — fix by hand before writing" % (f, err))
    head, guidance = ADDABLE[a.section]
    if section(body, head.lstrip("# ")) is not None:
        print("%s already has %s — nothing to do" % (f.stem, head))
        return
    # before ## Decisions & deviations if it exists, so the narrative sections stay together
    anchor = "\n## Decisions & deviations"
    block = "\n%s\n%s" % (head, guidance)
    new = body.replace(anchor, block + anchor, 1) if anchor in body else body.rstrip() + "\n" + block
    if write_fm(f, fm, new):
        print("%s: added %s" % (f.stem, head))


# ───────────────────────── R2: the handback

def cmd_handback(a):
    """What the next session cannot derive. Everything else in `wp brief` is computed, so this
    holds only the two things git and gh cannot answer: why you stopped, and whose turn it is."""
    info, d, f = _brief_target(a)
    fm, body, err = read_fm_strict(f)
    if err:
        die("%s: frontmatter did not parse (%s) — fix by hand before writing" % (f, err))
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["### %s" % stamp, "- **stopped:** %s" % a.stopped.strip()]
    if a.tried:
        lines.append("- **tried and abandoned:** %s" % a.tried.strip())
    lines.append("- **turn:** %s" % a.turn)
    entry = "\n".join(lines)

    head = "## Handback"
    if section(body, "Handback") is None:
        block = ("\n%s\n<!-- Append-only, newest first. Written by `wp handback`, never by hand.\n"
                 "     Sign-off never clears this section — a refuted approach is exactly what a\n"
                 "     later session needs and what ## Learnings would have deleted. -->\n\n%s\n" % (head, entry))
        anchor = "\n## Decisions & deviations"
        body = body.replace(anchor, block + anchor, 1) if anchor in body else body.rstrip() + "\n" + block
    else:
        m = re.search(r"^## Handback\b.*?$", body, re.M)
        insert = body.index("\n", m.end()) + 1
        after = body[insert:]
        cm = re.search(r"^<!--.*?-->\n", after, re.S)   # keep the guidance above the newest entry
        if cm:
            insert += cm.end()
        body = body[:insert] + "\n" + entry + "\n" + body[insert:]
    fm["updated"] = TODAY
    if write_fm(f, fm, body):
        print("%s: handback recorded (turn: %s)" % (f.stem, a.turn))


# ───────────────────────── S5 + C3: one decision verb, two modes

def _slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:60]


def cmd_decide(a):
    info = resolve(a.service) if a.service else locate(None)
    d = Path(info["vault"])
    if a.record:
        if not a.title:
            die("--record needs --title")
        dec = d / "decisions"
        dec.mkdir(parents=True, exist_ok=True)
        f = dec / ("%s-%s.md" % (TODAY, _slug(a.title)))
        if f.exists():
            die("%s already exists — supersede it with a new record and set its status, don't rewrite it" % rel(f))
        fm = {"tags": ["waypoint", info["service"], "decision"], "decided": TODAY, "status": "accepted"}
        if a.ticket:
            fm["ticket"] = a.ticket
        # deliberately no verified_sha/verified_paths: a decision record states what was decided
        # *then*. It is never wrong, only superseded — and superseding is a new file plus a
        # one-word status edit, never an in-place rewrite.
        write_fm(f, fm, "# %s\n\n## Context\n<!-- What forced a choice. -->\n\n"
                        "## Options considered\n<!-- Chosen first, then each rejected one, each with its because. -->\n\n"
                        "## Consequences\n<!-- Good, and the cost accepted. -->\n\n"
                        "## Confirmation\n<!-- The signal in prod that would show this was wrong. -->\n" % a.title)
        print(f)
        return

    if not a.text:
        die("give --text \"<what was decided and why>\", or --record --title \"...\" for a durable record")
    f = find_plan(d, a.plan) if a.plan else _brief_target(a)[2]
    fm, body, err = read_fm_strict(f)
    if err:
        die("%s: frontmatter did not parse (%s) — fix by hand before writing" % (f, err))
    who = (" (%s)" % a.who) if a.who else ""
    entry = "- **%s%s** — %s" % (TODAY, who, a.text.strip())
    head = "## Decisions & deviations"
    if section(body, "Decisions & deviations") is None:
        anchor = "\n## Learnings"
        block = "\n%s\n\n%s\n" % (head, entry)
        body = body.replace(anchor, block + anchor, 1) if anchor in body else body.rstrip() + "\n" + block
    else:
        m = re.search(r"^## Decisions & deviations\b.*?$", body, re.M)
        insert = body.index("\n", m.end()) + 1
        after = body[insert:]
        cm = re.search(r"^<!--.*?-->\n", after, re.S)
        if cm:
            insert += cm.end()
        body = body[:insert] + "\n" + entry + "\n" + body[insert:]
    # `updated:` was stamped in exactly one place in the whole CLI — cmd_plan_status — so a plan
    # worked hard all day never moved. Any decision recorded on it counts as movement.
    fm["updated"] = TODAY
    if write_fm(f, fm, body):
        print("%s: %s" % (f.stem, entry))


def cmd_tick(a):
    """Tick an increment and stamp the commit that closed it. The only change in this refit that
    removes a discipline rather than adding one: the stamp format becomes impossible to mistype."""
    info = resolve(a.service)
    d = Path(info["vault"])
    f = find_plan(d, a.plan)
    fm, body, err = read_fm_strict(f)
    if err:
        die("%s: frontmatter did not parse (%s) — fix by hand before writing" % (f, err))
    wt = a.worktree or git_cwd_for(fm, info)
    sha = a.sha
    if not sha and not is_config_only(fm):
        if not wt:
            die("no worktree to read HEAD from — pass --sha or --worktree")
        rc, sha, _ = sh(["git", "rev-parse", "--short", "HEAD"], cwd=wt)
        if rc != 0:
            die("could not read HEAD in %s — pass --sha" % wt)

    inc = section(body, "Increments")
    if inc is None:
        die("%s has no ## Increments section" % f.name)
    want = str(a.increment).rstrip(".")
    hit = None
    for line in inc.splitlines():
        m = re.match(r"^\s*[-*] \[([ xX])\]\s*([A-Za-z]*\d+[a-z]?)\.", line)
        if m and m.group(2).lower() == want.lower():
            hit = (line, m)
            break
    if hit is None:
        present = [mm.group(1) for mm in
                   (re.match(r"^\s*[-*] \[[ xX]\]\s*([A-Za-z]*\d+[a-z]?)\.", l) for l in inc.splitlines())
                   if mm]
        die("no increment %r in %s. Increments present: %s"
            % (want, f.name, ", ".join(present) or "(none numbered)"))
    line, m = hit
    new = line
    if m.group(1) == " ":
        new = re.sub(r"\[ \]", "[x]", new, count=1)
    if a.note:
        new = new.rstrip() + " — " + a.note.strip()
    if sha and sha not in new:
        new = new.rstrip() + " — done: %s" % sha
    if new == line:
        print("increment %s already ticked and stamped — nothing to do" % want)
        return
    if not write_fm(f, fm, body.replace(line, new, 1)):
        return
    record_plan_usage(info["service"], f.stem, want, fm)
    print("%s: %s" % (f.stem, new.strip()))


def cmd_signoff(a):
    info = resolve(a.service)
    d = Path(info["vault"])
    f = find_plan(d, a.plan)
    fm, body = read_fm(f)
    wt = a.worktree or git_cwd_for(fm, info)
    facts = plan_facts(fm, body, wt, vault_dir=d, plan_path=f)
    blockers, notes = gate(facts)

    print("plan: %s (status: %s)" % (f, fm.get("status")))
    print("worktree: %s | base: %s | pr: %s" % (wt, facts["base"], fm.get("pr") or "none"))

    if facts["config_only"]:
        print("\nmode: config-only (branch: %s) — skipping diff/uncommitted/commit-linkage checks; "
              "gating on Verification, increments, acceptance criteria" % fm.get("branch"))
    elif wt:
        print("\n--- actual diff vs %s ---" % facts["base"])
        print(facts["diff"]["stat"] or "(none / not resolvable)")
        changed = facts["diff"]["changed"]
        if changed:
            print("changed files: %d" % len(changed))
            for c in changed[:40]:
                print("  %s" % c)
            if len(changed) > 40:
                print("  ... %d more" % (len(changed) - 40))

    for x in facts["inc_unchecked"][:8]:
        print("  UNCHECKED %s" % x)
    for x in facts["ac_unmet"][:8]:
        print("  UNMET %s" % x)
    for i in facts["gates_unmet"][:8]:
        print("  GATE %s %s — %s" % (i["id"], "BREACHED (ticked!)" if i["ticked"] else "not met",
                                     i["gate"][:70]))
    for p in facts["placeholders"][:8]:
        print("  PLACEHOLDER %s" % re.sub(r"\s+", " ", p)[:60])

    if facts["learnings"]:
        print("\n--- learnings (promote into a durable doc, then clear) ---")
        print(facts["learnings"])

    if facts["rows"]:
        print("\n--- increments <-> commits ---")
        print("  %-4s %-11s %-10s %s" % ("#", "sha", "reachable", "in-diff"))
        for r in facts["rows"]:
            print("  %-4s %-11s %-10s %s" % r)

    if facts.get("touched_guardrails"):
        print("\n--- guardrails on the paths this diff touches ---")
        for g in facts["touched_guardrails"]:
            print("  [%s:%s] %s" % (g["kind"], g["id"], g["text"]))

    if facts["pr_src"] == "branch":
        print("\npr discovered from branch: #%s (created %s, %s) — record it: wp plan set-status … --pr %s"
              % (facts["pr"], facts["pr_disc"].get("createdAt"), facts["pr_disc"].get("state"), facts["pr"]))
    if facts["pr"]:
        print("\n--- pr ---")
        print(json.dumps(facts["pf"], indent=2))

    print("\n--- verdict ---")
    if blockers:
        print("BLOCKED — do not mark complete:")
        for b in blockers:
            print("  - %s" % b)
    else:
        print("PASS — gate clear; reconcile the plan against the diff above, then complete")
    for n in notes:
        print("  note: %s" % n)
    if blockers:
        sys.exit(2)


def cmd_system_list(a):
    rows = iter_systems()
    if not rows:
        print("no systems yet — wp system init <name>")
        return
    for name, d in rows:
        members = system_members(name)
        docs = [f.name for f in sorted(d.glob("*.md"))]
        onboarded = "" if (d / "system.yaml").exists() else "  [NO system.yaml]"
        print("%-16s %2d member%s  docs: %s%s"
              % (name, len(members), "" if len(members) == 1 else "s",
                 ", ".join(docs) or "(none)", onboarded))


def cmd_system_status(a):
    d = SYS / a.name
    if not d.is_dir():
        die("no such system: %s (wp system list)" % a.name)
    members = system_members(a.name)
    print("%s — %d member%s" % (a.name, len(members), "" if len(members) == 1 else "s"))
    docs = [f.name for f in sorted(d.glob("*.md"))]
    missing = [x for x in SYSTEM_DOCS if x not in docs]
    print("  docs:    %s" % (", ".join(docs) or "(none)"))
    if missing:
        print("  missing: %s" % ", ".join(missing))
    if not members:
        print("  no members — a service joins by declaring `system: %s` in its waypoint.yaml"
              % a.name)
        return
    by_type = {}
    for s, sd in members:
        try:
            wy = yaml.safe_load((sd / "waypoint.yaml").read_text()) or {}
        except Exception:
            wy = {}
        by_type.setdefault(str(wy.get("type") or "?"), []).append(s)
    for t in sorted(by_type):
        print("  %-9s %s" % (t, ", ".join(sorted(by_type[t]))))


def cmd_system_init(a):
    d = SYS / a.name
    d.mkdir(parents=True, exist_ok=True)
    sy = d / "system.yaml"
    if not sy.exists():
        atomic_write(sy, textwrap.dedent("""\
            # {name} — Waypoint system index. Cheap orientation only, never documentation.
            # Members are NOT listed here: a service joins by declaring `system: {name}` in its
            # own waypoint.yaml, so there is one source of truth. `wp system status {name}` reads it.
            system: {name}
            owner: {owner}
            purpose: >
              TODO one or two lines: what this system is for, and what is out of scope.
            created: {date}
            """).format(name=a.name, owner=a.owner or "TODO", date=TODAY))
    for doc in SYSTEM_DOCS:
        f = d / doc
        if f.exists():
            continue
        title = "%s — %s" % (a.name, doc[:-3].replace("-", " "))
        atomic_write(f, "---\ntags:\n- system\n- %s\nverified: '%s'\ntitle: %s\n---\n# %s\n\n"
                        "TODO\n" % (a.name, TODAY, title, title))
    print("initialised %s\n  docs: %s\n  members: declare `system: %s` in each service's waypoint.yaml"
          % (d, ", ".join(SYSTEM_DOCS), a.name))


def _services_for(a):
    if getattr(a, "service", None):
        info = resolve(a.service)
        return [(info["service"], Path(info["vault"]))]
    return iter_services()


def cmd_status(a):
    for s, d in _services_for(a):
        info = locate(s) if a.check_prs else None
        rows = []
        for f in plan_files(d):
            fm, _ = read_fm(f)
            st = fm.get("status", "?")
            if a.active_only and st not in OPEN_STATUSES:
                continue
            flag, warning = "", ""
            if a.check_prs and st in OPEN_STATUSES:
                r = unclosed_check(fm, info)
                if r.get("warning"):
                    warning = r["warning"]
                elif r.get("merged"):
                    flag = "  <<< UNCLOSED WAYPOINT: PR #%s merged (%s), plan still %s" % (r["pr"], r["source"], st)
            rows.append("  %-9s %-30s %s%s" % (st, f.stem, plan_date(fm), flag))
            if warning:
                rows.append("      !! %s: %s" % (f.stem, warning))
        if rows:
            print("%s" % s)
            print("\n".join(rows))


LIST_STATUS_ORDER = {"blocked": 0, "active": 1, "draft": 2}


def gather_fleet(services, net=True, workers=8):
    """Every open plan with its real state. Serial this is ~3.4s for seven plans, which is why
    nobody reaches for it casually; the gh calls are independent so they go in a pool."""
    jobs = []
    for s, d in services:
        info = locate(s)
        for f in plan_files(d):
            fm, body = read_fm(f)
            if fm.get("status") in OPEN_STATUSES:
                jobs.append((s, info, f, fm, body))

    def one(job):
        s, info, f, fm, body = job
        wt = git_cwd_for(fm, info)
        facts = plan_facts(fm, body, wt, net=net, vault_dir=Path(info["vault"]), plan_path=f)
        facts["service"] = s
        facts["stem"] = f.stem
        facts["turn"], facts["why"] = whose_turn(facts)
        return facts

    if not jobs:
        return []
    with ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as ex:
        return list(ex.map(one, jobs))


TURNS = ["YOUR TURN", "AN AGENT'S TURN", "WAITING ON A REVIEWER", "WAITING ON THE WORLD"]


def cmd_fleet(a):
    rows = gather_fleet(_services_for(a), net=not a.no_net)
    if a.json:
        for r in rows:
            r.pop("inc_section", None); r.pop("ac_section", None); r.pop("increments", None)
        print(json.dumps(rows, indent=2, default=str))
        return
    if not rows:
        print("no open plans — nothing in flight")
        return
    buckets = {k: [] for k in TURNS}
    buckets[None] = []
    for r in rows:
        buckets.setdefault(r["turn"], []).append(r)

    def pr_bit(r):
        pf = r["pf"] or {}
        if not r["pr"]:
            return "config-only" if r["config_only"] else "no PR"
        state = "MERGED" if pf.get("merged") else ("DRAFT" if pf.get("draft") else (pf.get("state") or "?"))
        extra = ""
        if pf.get("failing_checks"):
            extra = " x%d checks" % len(pf["failing_checks"])
        elif pf.get("review") == "CHANGES_REQUESTED":
            extra = " CHANGES_REQUESTED"
        elif pf.get("unresolved_threads"):
            extra = " %d threads" % pf["unresolved_threads"]
        return "#%s %s%s" % (r["pr"], state, extra)

    # paired plans (one ticket, several services) print as one block — today they land as
    # unrelated alphabetically-adjacent rows and read as two separate pieces of work
    for turn in TURNS:
        got = buckets.get(turn) or []
        if turn != "YOUR TURN" and not got and a.turn == "mine":
            continue
        if a.turn == "mine" and turn != "YOUR TURN":
            continue
        print("\n%s (%d)" % (turn, len(got)))
        seen = set()
        for r in sorted(got, key=lambda x: (str(x["ticket"] or "~"), x["service"])):
            tk = str(r["ticket"] or "")
            first = tk not in seen or not tk
            seen.add(tk)
            inc = "%d/%d inc" % (r["inc_ticked"], r["inc_ticked"] + len(r["inc_unchecked"]))
            print("  %-11s %-26s %-26s %s" % (tk if first else "", r["service"][:26], pr_bit(r), inc))
            if r["gates_unmet"]:
                print("  %-11s %-26s gate not met: %s" % ("", "", _first_line(r["gates_unmet"][0]["gate"], 40)))
    stray = buckets.get(None) or []
    if stray and a.turn != "mine":
        print("\nUNCLASSIFIED (%d)" % len(stray))
        for r in stray:
            print("  %-11s %-26s %s" % (r["ticket"] or "", r["service"][:26], pr_bit(r)))

    held = [r for r in rows if r["dev_hold"]]
    if held:
        print("\nSHARED DEV")
        for r in held:
            print("  %-26s held by %s" % (r["service"][:26], r["dev_hold"]))

    if a.turn != "mine":
        print("\nbucketing: red check / CHANGES_REQUESTED / unresolved thread / merged-but-unsigned "
              "-> yours; unticked increments -> an agent's; open+green+undecided -> a reviewer's; "
              "blocked -> the world's. Printed so a miscall is visibly wrong.")


def cmd_list(a):
    ticketed, untracked = [], []
    for s, d in _services_for(a):
        info = locate(s) if a.check_prs else None
        for f in plan_files(d):
            fm, _ = read_fm(f)
            st = fm.get("status", "?")
            if st not in LIST_STATUS_ORDER:
                continue
            ticket = str(fm.get("ticket") or "").strip()
            row = {"service": s, "stem": f.stem, "status": st, "ticket": ticket,
                   "title": fm.get("title") or f.stem, "when": plan_date(fm), "flag": "", "warn": ""}
            if a.check_prs:
                r = unclosed_check(fm, info)
                if r.get("warning"):
                    row["warn"] = r["warning"]
                elif r.get("merged"):
                    row["flag"] = "UNCLOSED WAYPOINT: PR #%s merged (%s), plan still %s" % (r["pr"], r["source"], st)
                if r.get("pr") and not r.get("merged"):
                    pf = pr_facts(r["pr"], git_cwd_for(fm, info))
                    bits = []
                    if pf.get("draft"):
                        bits.append("draft")
                    if pf.get("failing_checks"):
                        bits.append("%d failing" % len(pf["failing_checks"]))
                    if pf.get("review") == "CHANGES_REQUESTED":
                        bits.append("CHANGES_REQUESTED")
                    if pf.get("unresolved_threads"):
                        bits.append("%d thread(s)" % pf["unresolved_threads"])
                    row["pr_note"] = "#%s %s" % (r["pr"], ", ".join(bits)) if bits else ""
            (ticketed if ticket and ticket.lower() != "none" else untracked).append(row)

    def emit(heading, rows, show_ticket):
        print(heading)
        if not rows:
            print("  (none)")
            return
        if a.sort == "updated":
            rows.sort(key=lambda r: (r["service"], r["stem"]))          # stable tie-break, ascending
            rows.sort(key=lambda r: r["when"], reverse=True)            # newest first
        else:
            rows.sort(key=lambda r: (LIST_STATUS_ORDER.get(r["status"], 9), r["service"], r["stem"]))
        shown = rows[:a.limit] if a.limit else rows
        for r in shown:
            head = "%-9s %-16s" % (r["status"], r["service"])
            if show_ticket:
                head += " %-12s" % r["ticket"]
            print("  %s %-32s %s" % (head, r["title"][:32], r["when"]))
            if r.get("pr_note"):
                print("      -> %s" % r["pr_note"])
            if r["flag"]:
                print("      <<< %s" % r["flag"])
            if r["warn"]:
                print("      !! %s" % r["warn"])
        if len(rows) > len(shown):
            print("  (%d more)" % (len(rows) - len(shown)))

    emit("=== Ticketed work ===", ticketed, True)
    print()
    emit("=== Non-ticketed work ===", untracked, False)


def cmd_index(a):
    if not ENG.is_dir():
        die("no %s yet" % ENG)
    lines = ["---", "tags: [waypoint]", "---", "# Engineering", "",
             "One folder per service. Inside each:", "",
             "- `waypoint.yaml` — cheap orientation index (not documentation)",
             "- `overview.md` / `architecture.md` / `known-context.md` (+ optional "
             "`operations.md`, `testing.md`, `interfaces.md`, `design.md`) — durable context",
             "- `plans/` — what we intend to do, and what is happening now",
             "- `ledger.md` — agent-facing record of meaningful work, newest first",
             "- `explainers/` — human-facing current system truth", "",
             "Source is implementation truth. Git is forensic truth. Plans describe intended and",
             "current work. The ledger records completed work. Explainers describe the system as",
             "it is now. Regenerate this page with `wp index`; check health with `wp doctor`.", "",
             "| Service | Type | Docs | Explainers | Active plans | Last work |",
             "| --- | --- | --- | --- | --- | --- |"]
    for name, p in iter_services():
        wy = p / "waypoint.yaml"
        meta = {}
        if wy.exists():
            try:
                meta = yaml.safe_load(wy.read_text()) or {}
            except yaml.YAMLError as e:
                warn("%s: bad yaml — %s" % (rel(wy), str(e).splitlines()[0]))
            if not isinstance(meta, dict):
                meta = {}
        docs = len([f for f in p.glob("*.md") if f.name not in NON_DOC_FILES])
        ex = len(list((p / "explainers").glob("*.md"))) if (p / "explainers").is_dir() else 0
        act = 0
        for f in plan_files(p):
            fm, _ = read_fm(f)
            if fm.get("status") in OPEN_STATUSES:
                act += 1
        last = last_activity(p)
        lines.append("| [[Engineering/%s/overview\\|%s]] | %s | %d | %d | %d | %s |"
                     % (name, name, meta.get("type", "?"), docs, ex, act, last))
    atomic_write(ENG / "index.md", "\n".join(lines) + "\n")
    print("wrote %s" % (ENG / "index.md"))


# --------------------------------------------------------------------- doctor

DOCTOR_SECTIONS = [
    ("UNCLOSED", "plan still open but its PR is merged"),
    ("STALE-PLAN", "active/blocked and not updated within the window"),
    ("PR-DRIFT", "plan's PR was closed without merging"),
    ("STALE-DOC", "commits on verified_paths since verified_sha"),
    ("NO-SHA", "ticked increment carrying no commit sha — tick with wp tick"),
    ("STALE-SNAPSHOT", "a dated (snapshot ...) claim in known-context.md older than the window"),
    ("NO-ANCHOR", "doc has no resolvable verified_sha"),
    ("ORPHAN-ANCHOR", "verified_sha is not on the default branch — staleness is unmeasurable"),
    ("BAD-YAML", "frontmatter or waypoint.yaml does not parse"),
    ("NUMERIC-SHA", "verified_sha parsed as a number"),
    ("NOT-ONBOARDED", "folder exists but has no waypoint.yaml"),
    ("STALE-PROGRAMME", "multi-repo programme not updated within the window"),
]
# STALE-DOC gates only for a service with an open plan. The morning digest already applies that
# rule by hand ("FYI unless the service has an active plan"); with 16 standing findings the day
# after a full sweep, a report that is red every morning for the same rows is not an alarm.
DOCTOR_EXIT2 = {"UNCLOSED", "BAD-YAML", "ORPHAN-ANCHOR"}


def cmd_doctor(a):
    findings = {s: [] for s, _ in DOCTOR_SECTIONS}
    warnings = []

    def add(sec, service, item, detail, fix, **extra):
        findings[sec].append(dict(service=service, item=item, detail=detail, fix=fix, **extra))

    services = _services_for(a)
    fetched = set()
    for name, d in services:
        info = locate(name)
        has_open_plan = any(read_fm(p)[0].get("status") in OPEN_STATUSES for p in plan_files(d))
        repo = Path(info["repo"]) if info["repo"] and Path(info["repo"]).is_dir() else None
        if repo and not a.no_fetch and str(repo) not in fetched:
            fetch_origin(repo)
            fetched.add(str(repo))

        wy = d / "waypoint.yaml"
        if not wy.exists():
            add("NOT-ONBOARDED", name, "waypoint.yaml", "folder exists but was never onboarded",
                "run waypoint-onboard %s, or delete the folder" % name)
        else:
            try:
                meta = yaml.safe_load(wy.read_text())
                if meta is not None and not isinstance(meta, dict):
                    raise yaml.YAMLError("not a mapping")
            except yaml.YAMLError as e:
                add("BAD-YAML", name, "waypoint.yaml", str(e).splitlines()[0][:120], "fix the YAML by hand")

        for f in sorted(d.glob("*.md")):
            if f.name in NON_DOC_FILES:
                continue
            data, body, err, raw = load_fm(f)
            if data is None:
                add("BAD-YAML", name, f.name, err[:120], "fix the frontmatter by hand")
                continue
            if f.name == "known-context.md":
                continue
            rawsha = data.get("verified_sha")
            if isinstance(rawsha, (int, float)) and not isinstance(rawsha, bool):
                add("NUMERIC-SHA", name, f.name, "verified_sha: %r (unquoted digits)" % rawsha, "wp sync %s" % name)
            fm = norm_fm(dict(data), raw)
            sha = str(fm.get("verified_sha") or "")
            paths = ",".join(str(p) for p in (fm.get("verified_paths") or []))
            if not sha or sha == "unknown":
                add("NO-ANCHOR", name, f.name, "no verified_sha",
                    "wp verify %s %s --paths ..." % (name, f.name))
                continue
            if repo and anchor_ancestry(repo, sha, default_branch_ref(repo)) == "off-branch":
                add("ORPHAN-ANCHOR", name, f.name,
                    "anchor %s is not an ancestor of %s (pre-squash or rebased commit)"
                    % (sha[:9], default_branch_ref(repo)),
                    "wp verify %s %s --paths %s" % (name, f.name, paths or "..."))
                continue
            n, _ = doc_staleness(repo, fm)
            if n is None:
                add("NO-ANCHOR", name, f.name,
                    "sha %s not resolvable in %s" % (sha[:9], repo or "no repo (set repo: in waypoint.yaml?)"),
                    "wp verify %s %s --paths %s" % (name, f.name, paths or "..."))
            elif n > 0:
                _, subjects = doc_staleness(repo, fm, limit=5)
                add("STALE-DOC", name, f.name, "%d commit(s) since %s on %s" % (n, sha[:9], paths or "<repo>"),
                    "wp stale %s; update the doc, then wp verify %s %s --paths %s"
                    % (name, name, f.name, paths or "..."), commits=n,
                    gating=has_open_plan, subjects=subjects)

        wy_data = read_fm(d / "waypoint.yaml")[0] if (d / "waypoint.yaml").exists() else {}
        cfm = commands_fm(wy_data)
        if wy_data.get("commands") is not None and cfm["verified_sha"]:
            cn, _ = doc_staleness(repo, cfm)
            if cn:
                _, csub = doc_staleness(repo, cfm, limit=5)
                add("STALE-DOC", name, "waypoint.yaml (commands)",
                    "%d commit(s) since %s on %s" % (cn, str(cfm["verified_sha"])[:9],
                                                     ",".join(str(p) for p in cfm["verified_paths"])),
                    "check the scripts still match, then wp verify %s commands --paths %s"
                    % (name, ",".join(str(p) for p in cfm["verified_paths"])),
                    commits=cn, gating=has_open_plan, subjects=csub)

        for s in snapshots(d):
            if s["age"] > SNAPSHOT_DAYS:
                add("STALE-SNAPSHOT", name, "known-context.md",
                    "snapshot %s is %dd old: %s" % (s["date"], s["age"], s["text"]),
                    "re-check the claim against reality, then restate it with today's date "
                    "(or delete it if it has stopped mattering)", age_days=s["age"])

        for f in plan_files(d):
            item = "plans/" + f.name
            data, body, err, raw = load_fm(f)
            if data is None:
                add("BAD-YAML", name, item, err[:120], "fix the frontmatter by hand")
                continue
            fm = norm_fm(dict(data), raw)
            st = fm.get("status")
            if st not in OPEN_STATUSES:
                continue
            if not is_config_only(fm):
                inc = section(body, "Increments") or ""
                bare = [m.group(1) or "?" for m in
                        (TICKED_RE.match(l) for l in inc.splitlines()) if m and not DONE_RE.search(m.group(2))]
                if bare:
                    add("NO-SHA", name, item, "%d ticked increment(s) with no sha: %s"
                        % (len(bare), ", ".join(bare[:8])),
                        "wp tick %s --plan %s --increment <id>" % (name, f.stem), count=len(bare))
            if st in ("active", "blocked") and fm.get("updated"):
                try:
                    age = (dt.date.today() - dt.date.fromisoformat(str(fm["updated"])[:10])).days
                except ValueError:
                    age = None
                if age is not None and age > a.stale_days:
                    add("STALE-PLAN", name, item, "updated %s (%dd ago), status %s" % (fm["updated"], age, st),
                        "continue it (waypoint-work %s), or set-status blocked/abandoned" % f.stem,
                        updated=str(fm["updated"]), age_days=age)
            r = unclosed_check(fm, info)
            if r.get("warning"):
                warnings.append({"service": name, "item": item, "message": r["warning"]})
                continue
            if r.get("pr"):
                if r.get("merged"):
                    add("UNCLOSED", name, item, "PR #%s MERGED (%s), plan still %s" % (r["pr"], r["source"], st),
                        "wp signoff %s --plan %s" % (name, f.stem),
                        pr={"number": r["pr"], "state": r.get("state"), "url": r.get("url"), "source": r["source"]})
                elif r.get("state") == "CLOSED":
                    add("PR-DRIFT", name, item, "PR #%s CLOSED without merge (%s)" % (r["pr"], r["source"]),
                        "abandon the plan (set-status abandoned), or re-open/relink the PR",
                        pr={"number": r["pr"], "state": r.get("state"), "url": r.get("url"), "source": r["source"]})

    # Programmes are vault-wide, not per-service — only scan on a whole-vault run.
    if not getattr(a, "service", None):
        for pname, pfile, pfm, perr in iter_programmes():
            if perr:
                add("BAD-YAML", pname, pfile.name, perr[:120], "fix the frontmatter by hand")
                continue
            status = str(pfm.get("status") or "unknown")
            if PROGRAMME_DONE.search(status):
                continue
            upd = str(pfm.get("updated") or "")
            try:
                age = (dt.date.today() - dt.date.fromisoformat(upd[:10])).days
            except ValueError:
                age = None
            if age is None:
                add("STALE-PROGRAMME", pname, pfile.name,
                    "status %s, no readable `updated` date" % status,
                    "set `updated:` on the state doc so it can be tracked")
            elif age > a.stale_days:
                add("STALE-PROGRAMME", pname, pfile.name,
                    "status %s, updated %s (%dd ago)" % (status, upd, age),
                    "pick it up, or set status to complete/abandoned if it is finished",
                    updated=upd, age_days=age, status=status)

    counts = {s: len(v) for s, v in findings.items()}
    code = 2 if any(counts[s] for s in DOCTOR_EXIT2) else 0
    if any(r.get("gating") for r in findings["STALE-DOC"]):
        code = 2

    if a.json:
        print(json.dumps({"date": TODAY, "services": len(services), "fetched": not a.no_fetch,
                          "stale_days": a.stale_days, "findings": findings, "warnings": warnings,
                          "counts": counts, "exit": code}, indent=2, default=str))
    else:
        nprog = 0 if getattr(a, "service", None) else len(iter_programmes())
        print("wp doctor — %d service(s), %d programme(s), %d repo(s) %s, %s, stale-days %d"
              % (len(services), nprog, len(fetched),
                 "fetched" if not a.no_fetch else "not fetched (--no-fetch)", TODAY, a.stale_days))
        for sec, meaning in DOCTOR_SECTIONS:
            rows = findings[sec]
            print("\n%s (%d)%s" % (sec, len(rows), " — " + meaning if rows else ""))
            for r in rows:
                mark = "  <-- service has an open plan" if r.get("gating") else ""
                print("  %-19s %-48s %s%s" % (r["service"], r["item"], r["detail"], mark))
                for s in (r.get("subjects") or [])[:5]:
                    print("  %-19s   %s" % ("", s))
                print("  %-19s fix: %s" % ("", r["fix"]))
        if warnings:
            print("\nwarnings (%d)" % len(warnings))
            for w in warnings:
                print("  %-19s %-48s %s" % (w["service"], w["item"], w["message"]))
        print("\nsummary: %s -> exit %d"
              % (" | ".join("%s %d" % (s, counts[s]) for s, _ in DOCTOR_SECTIONS), code))
    if code:
        sys.exit(code)


def cmd_sync(a):
    """Mechanical fixes only: backfill `pr:` from the branch, un-number a verified_sha.
    Never changes status or a body. Reads normalise types anyway, so nothing else is rewritten."""
    changed = skipped = 0
    for name, d in _services_for(a):
        info = locate(name)
        files = [f for f in sorted(d.glob("*.md")) if f.name not in NON_DOC_FILES] + plan_files(d)
        for f in files:
            data, body, err, raw = load_fm(f)
            if err == "no frontmatter block":
                continue
            if data is None:
                skipped += 1
                print("  skip (bad yaml): %s — %s" % (rel(f), err))
                continue
            fm = dict(data)
            changes = []
            for k in ("verified_sha", "base_sha"):
                v = fm.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    fm[k] = _raw_token(raw, k) or str(v)
                    changes.append((k, v, fm[k]))
            if f.parent.name == "plans" and not fm.get("pr") and str(fm.get("status")) != "abandoned":
                nf = norm_fm(dict(fm), raw)
                cwd = git_cwd_for(nf, info)
                if cwd:
                    pr, src, facts = plan_pr(nf, cwd)
                    if src == "branch":
                        fm["pr"] = str(pr)
                        changes.append(("pr", None, fm["pr"]))
                    elif src == "error":
                        warn("%s: PR discovery failed: %s" % (rel(f), facts.get("error")))
            if changes:
                if not a.dry_run:
                    # PR discovery above shells out to `gh` (~0.4s). Re-read here so an edit made
                    # during that window is preserved: only the frontmatter keys this sweep
                    # actually changed are re-applied, onto whatever the body is now.
                    fresh, body, ferr, fraw = load_fm(f)
                    if fresh is None:
                        skipped += 1
                        print("  skip (bad yaml on re-read): %s — %s" % (rel(f), ferr))
                        continue
                    for k, _old, new in changes:
                        fresh[k] = new
                    if not write_fm(f, fresh, body, on_conflict="skip"):
                        skipped += 1
                        continue
                changed += 1
                print("  ~ %s: %s" % (rel(f), "; ".join("%s %r -> %r" % c for c in changes)))
    print("sync: %d file(s) changed, %d skipped (bad yaml)%s" % (changed, skipped, " (dry-run)" if a.dry_run else ""))
    if not a.dry_run and not getattr(a, "service", None):
        cmd_index(a)


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(prog="wp", description="Waypoint vault helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("locate", help="resolve service/repo/vault from a path or name")
    p.add_argument("target", nargs="?")
    p.set_defaults(fn=cmd_locate)

    p = sub.add_parser("find", help="which service's plan tracks a ticket, across the whole vault")
    p.add_argument("ticket")
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("init", help="create the vault folder, index and ledger")
    p.add_argument("service", nargs="?")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("context", help="the orientation bundle: index, doc staleness, manifest")
    p.add_argument("--paths", help="paths you are about to touch — prints only the guardrails on them")
    p.add_argument("service", nargs="?")
    p.add_argument("--plan", help="also print this plan in full (file stem, or a ticket that prefixes it)")
    p.set_defaults(fn=cmd_context)

    p = sub.add_parser("stale", help="which docs are behind their verified paths (exit 3 if any)")
    p.add_argument("--json", action="store_true")
    p.add_argument("service", nargs="?")
    p.set_defaults(fn=cmd_stale)

    p = sub.add_parser("verify", help="re-anchor a doc to the current sha")
    p.add_argument("service")
    p.add_argument("doc")
    p.add_argument("--paths", help="comma-separated repo paths this doc describes")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("plan", help="create a plan / set its status")
    ps = p.add_subparsers(dest="pcmd", required=True)
    q = ps.add_parser("new")
    q.add_argument("service", nargs="?")
    q.add_argument("--ticket")
    q.add_argument("--title", required=True)
    q.add_argument("--base", help="base ref (default: origin's default branch)")
    q.add_argument("--config-only", action="store_true", dest="config_only",
                   help="no code change expected: stamp branch/worktree as none so signoff gates on Verification/increments/ACs")
    q.add_argument("--no-git", action="store_true", dest="no_git",
                   help="don't read branch/worktree from cwd (idea stubs)")
    q.add_argument("--programme", help="the programme this plan is a promoted unit of")
    q.add_argument("--unit", help="the programme unit id this plan implements (e.g. E3)")
    q.set_defaults(fn=cmd_plan_new)
    q = ps.add_parser("add-section", help="add an on-demand section (kept out of the default template)")
    q.add_argument("service", nargs="?")
    q.add_argument("--plan", required=True)
    q.add_argument("section", choices=sorted(ADDABLE))
    q.set_defaults(fn=cmd_add_section)
    q = ps.add_parser("set-status")
    q.add_argument("service", nargs="?")
    q.add_argument("--plan", required=True)
    q.add_argument("--status", required=True,
                   choices=["draft", "active", "blocked", "complete", "abandoned"])
    q.add_argument("--reason", help="why — required for blocked/abandoned; stamped as reason: "
                                    "(plus blocked_since: for blocked, so its age is visible)")
    q.add_argument("--pr")
    q.set_defaults(fn=cmd_plan_status)
    q = ps.add_parser("set-model", help="record the recommended implementation model/effort tier on a plan")
    q.add_argument("service", nargs="?")
    q.add_argument("--plan", required=True)
    q.add_argument("--model", choices=["opus", "sonnet", "haiku"],
                   help="capability tier for implementing this plan (version-agnostic)")
    q.add_argument("--effort", choices=["low", "medium", "high"],
                   help="reasoning/thinking budget the implementation warrants")
    q.set_defaults(fn=cmd_plan_set_model)

    p = sub.add_parser("programme", help="scaffold / read / advance a multi-unit programme")
    gs = p.add_subparsers(dest="gcmd", required=True)
    g = gs.add_parser("new", help="scaffold Bifrost/<Name>/ (Overview + Migration State) from template")
    g.add_argument("name")
    g.add_argument("--owner")
    g.add_argument("--service", action="append", help="a service the programme spans (repeatable)")
    g.set_defaults(fn=cmd_programme_new)
    g = gs.add_parser("status", help="unit counts by state and group, and the next unblocked unit")
    g.add_argument("name")
    g.set_defaults(fn=cmd_programme_status, no_net=True, json=False)
    g = gs.add_parser("next", help="the next unblocked unit(s): todo with every dependency merged")
    g.add_argument("name")
    g.set_defaults(fn=cmd_programme_next, no_net=True, json=False)
    g = gs.add_parser("tick", help="advance a unit's status (and PR link) in the ledger")
    g.add_argument("name")
    g.add_argument("--unit", required=True)
    g.add_argument("--status", required=True,
                   choices=["todo", "doing", "done", "blocked", "deferred", "dropped", "rescoped"])
    g.add_argument("--pr", help="value for the PR cell, verbatim (e.g. '#84' or '[#84](url)')")
    g.set_defaults(fn=cmd_programme_tick, no_net=True, json=False)
    g = gs.add_parser("set-model", help="record a unit's recommended implementation model/effort tier in the ledger")
    g.add_argument("name")
    g.add_argument("--unit", required=True)
    g.add_argument("--model", choices=["opus", "sonnet", "haiku"],
                   help="recommended implementation model tier for the unit")
    g.add_argument("--effort", choices=["low", "medium", "high"],
                   help="recommended implementation effort for the unit")
    g.set_defaults(fn=cmd_programme_set_model, no_net=True, json=False)

    p = sub.add_parser("ledger", help="prepend an entry (agent-facing record)")
    p.add_argument("service", nargs="?")
    p.add_argument("--ticket")
    p.add_argument("--title", required=True)
    p.add_argument("--date")
    p.add_argument("--body", help="entry body; omit to read stdin")
    p.add_argument("--force", action="store_true", help="append even if the newest entry has the same heading")
    p.add_argument("--programme", help="the programme this work belongs to (its Bifrost/ folder name); orient prices the session against it")
    p.set_defaults(fn=cmd_ledger)

    p = sub.add_parser("idea", help="log a kept/discarded idea from waypoint-ideate")
    p.add_argument("service", nargs="?")
    p.add_argument("--title", required=True)
    p.add_argument("--status", required=True, choices=["kept", "discarded"])
    p.add_argument("--source", required=True, choices=["techdebt", "evolution", "user"])
    p.add_argument("--reason", required=True, help="why kept/discarded, one or two sentences")
    p.add_argument("--plan", help="plan file stem created for this idea, if kept")
    p.add_argument("--force", action="store_true", help="append even if the newest entry has the same heading")
    p.set_defaults(fn=cmd_idea)

    p = sub.add_parser("fleet", help="every open plan across the vault, grouped by whose turn it is")
    p.add_argument("service", nargs="?")
    p.add_argument("--turn", choices=["mine"], help="only what is waiting on you")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-net", action="store_true", dest="no_net")
    p.set_defaults(fn=cmd_fleet)

    p = sub.add_parser("handback", help="what the next session can't derive: why you stopped, whose turn")
    p.add_argument("service", nargs="?")
    p.add_argument("--plan")
    p.add_argument("--stopped", required=True, help="where this stops, and what it is waiting on")
    p.add_argument("--turn", required=True, choices=["me", "agent", "reviewer", "world"])
    p.add_argument("--tried", help="an approach tried and abandoned — the thing Learnings would delete")
    p.add_argument("--worktree")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--no-net", action="store_true", dest="no_net", help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_handback, no_net=True, json=False)

    p = sub.add_parser("decide", help="record a decision on a plan, or as a durable record")
    p.add_argument("service", nargs="?")
    p.add_argument("--plan")
    p.add_argument("--text", help="in-flight: one line into ## Decisions & deviations")
    p.add_argument("--who", help="who decided, when it wasn't you")
    p.add_argument("--record", action="store_true", help="durable: a dated file under decisions/")
    p.add_argument("--title", help="record mode: the decision, stated as a claim")
    p.add_argument("--ticket")
    p.add_argument("--worktree")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--no-net", action="store_true", dest="no_net", help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_decide, no_net=True, json=False)

    p = sub.add_parser("tick", help="tick an increment and stamp the commit that closed it")
    p.add_argument("service", nargs="?")
    p.add_argument("--plan", required=True)
    p.add_argument("--increment", required=True, help="the increment's id, e.g. 3 or W3 or 1b")
    p.add_argument("--sha", help="default: short HEAD in the plan's worktree")
    p.add_argument("--worktree")
    p.add_argument("--note", help="at most one line of what was verified")
    p.set_defaults(fn=cmd_tick)

    p = sub.add_parser("brief", help="one screen: where this plan is, and whose turn it is")
    p.add_argument("service", nargs="?")
    p.add_argument("--plan")
    p.add_argument("--worktree")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-net", action="store_true", dest="no_net",
                   help="skip the gh calls (no PR state, no dev hold)")
    p.set_defaults(fn=cmd_brief)

    p = sub.add_parser("signoff", help="collect the real facts and gate completion (exit 2 if BLOCKED)")
    p.add_argument("service", nargs="?")
    p.add_argument("--plan", required=True)
    p.add_argument("--worktree")
    p.set_defaults(fn=cmd_signoff)

    p = sub.add_parser("status", help="plans by state; --check-prs finds unclosed waypoints")
    p.add_argument("service", nargs="?")
    p.add_argument("--check-prs", action="store_true", dest="check_prs")
    p.add_argument("--active-only", action="store_true", dest="active_only")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("list", help="outstanding plans (active/blocked/draft), ticketed vs non-ticketed")
    p.add_argument("service", nargs="?")
    p.add_argument("--check-prs", action="store_true", dest="check_prs")
    p.add_argument("--sort", choices=["status", "updated"], default="status")
    p.add_argument("--limit", type=int)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("index", help="regenerate Engineering/index.md")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("doctor", help="read-only vault health report (exit 2 on UNCLOSED/BAD-YAML/STALE-DOC)")
    p.add_argument("service", nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument("--stale-days", type=int, default=7, dest="stale_days")
    p.add_argument("--no-fetch", action="store_true", dest="no_fetch")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("system", help="the level above a service: a system and its member services")
    ss = p.add_subparsers(dest="scmd", required=True)
    g = ss.add_parser("list", help="every system, member count and docs")
    g.set_defaults(fn=cmd_system_list)
    g = ss.add_parser("status", help="one system: its docs and members grouped by type")
    g.add_argument("name")
    g.set_defaults(fn=cmd_system_status)
    g = ss.add_parser("init", help="scaffold Systems/<name>/ (system.yaml + docs)")
    g.add_argument("name")
    g.add_argument("--owner")
    g.set_defaults(fn=cmd_system_init)

    p = sub.add_parser("sync", help="mechanical fixes: backfill pr: from the branch, fix numeric shas, reindex")
    p.add_argument("service", nargs="?")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.add_argument("--quiet", action="store_true", help="(reserved) only changed files and the summary are printed anyway")
    p.set_defaults(fn=cmd_sync)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
