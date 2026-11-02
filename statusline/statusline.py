#!/usr/bin/env python3
"""Claude Code status line: current-session usage, weekly usage, memory, CPU.

Reads Claude Code's status-line JSON on stdin (rate_limits + context_window come
from there, verbatim from the API) and reports the Claude process's own memory
and CPU from /proc. Every facet degrades to '—' on error and the script never
raises, so a bad read can never block the TUI.
"""
import json
import os
import sys
import time

CACHE = f"/tmp/claude-statusline-cpu-{os.environ.get('USER', 'x')}"
RESET = "\033[0m"
DIM = "\033[2m"
GREEN, YELLOW, RED = "\033[32m", "\033[33m", "\033[31m"


def load():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def dig(obj, *keys):
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def tone(pct, warn=50, bad=80):
    if pct is None:
        return DIM
    return RED if pct >= bad else YELLOW if pct >= warn else GREEN


def pct(value):
    v = num(value)
    return f"{round(v)}%" if v is not None else "—"


def reset_in(epoch):
    ts = num(epoch)
    if ts is None:
        return ""
    left = int(ts - time.time())
    if left <= 0:
        return ""
    if left >= 86400:
        return f"{DIM} {left // 86400}d{RESET}"
    if left >= 3600:
        return f"{DIM} {left // 3600}h{RESET}"
    return f"{DIM} {max(1, left // 60)}m{RESET}"


def ppid_of(pid):
    try:
        raw = open(f"/proc/{pid}/stat").read()
        return int(raw[raw.rfind(")") + 1 :].split()[1])
    except Exception:
        return None


# The claude process itself, not a wrapper shell — matched by process name / arg0,
# never a bare 'claude' substring (a wrapper's cmdline references ~/.claude and would false-match).
def is_claude(pid):
    try:
        raw = open(f"/proc/{pid}/stat").read()
        if raw[raw.find("(") + 1 : raw.rfind(")")] == "claude":
            return True
    except Exception:
        pass
    try:
        args = open(f"/proc/{pid}/cmdline").read().split("\0")
    except Exception:
        return False
    arg0 = os.path.basename(args[0]) if args and args[0] else ""
    return arg0 == "claude" or any("cli.js" in a for a in args)


# Walk up from this script through any wrapper shells to the Claude process.
def claude_pid():
    pid = os.getppid()
    for _ in range(8):
        if pid is None or pid <= 1:
            break
        if is_claude(pid):
            return pid
        pid = ppid_of(pid)
    return os.getppid()


def rss_mb(pid):
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except Exception:
        return None
    return None


def proc_jiffies(pid):
    try:
        raw = open(f"/proc/{pid}/stat").read()
        after = raw[raw.rfind(")") + 1 :].split()
        return int(after[11]) + int(after[12])  # utime + stime
    except Exception:
        return None


# CPU% of one core, from the jiffy delta between two status-line renders (cached).
# The cache carries the pid so a resolved-pid change never compares two processes,
# and a >60s gap is discarded so a stale sample can't spike the number.
def cpu_pct(pid, session):
    now = time.time()
    jiffies = proc_jiffies(pid)
    if jiffies is None:
        return None
    path = f"{CACHE}-{session}"
    prev = None
    try:
        pj, pt, pp = open(path).read().split()
        if int(pp) == pid:
            prev = (int(pj), float(pt))
    except Exception:
        prev = None
    try:
        with open(path, "w") as f:
            f.write(f"{jiffies} {now} {pid}")
    except Exception:
        pass
    if prev is None:
        return None
    dj, dt = jiffies - prev[0], now - prev[1]
    if dt <= 0 or dt > 60 or dj < 0:
        return None
    return 100.0 * (dj / os.sysconf("SC_CLK_TCK")) / dt


def mem_str(mb):
    if mb is None:
        return "—"
    return f"{mb / 1024:.1f}GB" if mb >= 1024 else f"{round(mb)}MB"


# orient's state dir (matches the app's config): where per-session snapshots are written so orient
# can show session status even after the terminal is closed.
def state_dir():
    return os.environ.get("ORIENT_STATE_DIR") or os.path.join(
        os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "orient"
    )


def sessions_dir():
    return os.path.join(state_dir(), "sessions")


# Read the previous snapshot's cost, if any, so persist() can tell whether cost actually moved
# before deciding to append a history row. A missing/unreadable file just means "no prior cost".
def prev_cost_usd(path):
    try:
        with open(path) as f:
            return num(json.load(f).get("cost_usd"))
    except Exception:
        return None


# Append-only usage history, throttled to one row per real cost change (not per 5s tick) — a long
# session would otherwise write thousands of near-duplicate rows. orient reads this to reconstruct
# how cost accumulated over a session's life, joined against wp tick's plan-usage.jsonl by
# session_id to show recommended-vs-actual model/effort/cost per plan.
def append_history(snapshot):
    cost = snapshot.get("cost_usd")
    if cost is None:
        return
    try:
        path = os.path.join(sessions_dir(), f"{snapshot['session_id']}.json")
        if cost == prev_cost_usd(path):
            return
        d = state_dir()
        os.makedirs(d, exist_ok=True)
        row = {
            "session_id": snapshot["session_id"],
            "model": snapshot.get("model"),
            "cost_usd": cost,
            "ts": snapshot["updated_at"],
        }
        with open(os.path.join(d, "usage-history.jsonl"), "a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


# Additive to the printed line: drop a snapshot orient reads. Fully guarded — a write failure never
# affects the status line.
def persist(snapshot):
    try:
        append_history(snapshot)
        d = sessions_dir()
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{snapshot['session_id']}.json")
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(snapshot, f)
        os.replace(tmp, path)
    except Exception:
        pass


def main():
    data = load()
    session = str(dig(data, "session_id") or "default").replace("/", "_")[:64]
    pid = claude_pid()

    model = dig(data, "model", "display_name") or dig(data, "model", "id") or ""
    sess = num(dig(data, "rate_limits", "five_hour", "used_percentage"))
    week = num(dig(data, "rate_limits", "seven_day", "used_percentage"))
    ctx = num(dig(data, "context_window", "used_percentage"))
    mem = rss_mb(pid)
    cpu = cpu_pct(pid, session)

    persist(
        {
            "session_id": session,
            "session_name": dig(data, "session_name"),
            "model": model or None,
            "cwd": dig(data, "workspace", "current_dir") or dig(data, "workspace", "project_dir"),
            "session_pct": sess,
            "session_resets_at": num(dig(data, "rate_limits", "five_hour", "resets_at")),
            "weekly_pct": week,
            "weekly_resets_at": num(dig(data, "rate_limits", "seven_day", "resets_at")),
            "ctx_pct": ctx,
            "cost_usd": num(dig(data, "cost", "total_cost_usd")),
            "mem_mb": round(mem) if mem is not None else None,
            "cpu_pct": round(cpu, 1) if cpu is not None else None,
            "pid": pid,
            "updated_at": int(time.time()),
        }
    )

    parts = []
    if model:
        parts.append(f"{DIM}{model}{RESET}")
    parts.append(f"{tone(sess)}sess {pct(sess)}{RESET}{reset_in(dig(data, 'rate_limits', 'five_hour', 'resets_at'))}")
    parts.append(f"{tone(week)}wk {pct(week)}{RESET}{reset_in(dig(data, 'rate_limits', 'seven_day', 'resets_at'))}")
    parts.append(f"{tone(ctx, 70, 90)}ctx {pct(ctx)}{RESET}")
    parts.append(f"mem {mem_str(mem)}")
    parts.append(f"{tone(cpu)}cpu {pct(cpu)}{RESET}")
    sys.stdout.write(f"{DIM} · {RESET}".join(parts))


try:
    main()
except Exception:
    sys.stdout.write("")
