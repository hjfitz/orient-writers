#!/usr/bin/env bash
# Rename a tmux window to "[FUSE-xyz] service — words", derived from a directory's
# git repo + branch. Shared engine for the /rename-tab skill, the Claude Stop hook,
# and (optionally) a shell precmd. Always exits 0 so it can never break a hook.
#
# Usage:
#   rename-tab.sh [--dir <dir>] [--repo <name>] [--pane <pane>] [--words "<words>"] [--sticky] [--dry-run]
#
#   (no args)        derive everything for the current pane's window (the hook path)
#   --repo "<name>"  the repo being worked on, resolved under the pane dir / ~/code/fuse.
#                    Use this when the shell sits in a parent dir (e.g. ~/code/fuse) but
#                    the work is in a specific repo — the label still gets [FUSE-xyz] service.
#   --dir  "<dir>"   derive from an explicit directory (lower-level; --repo is usually easier)
#   --words "..."    override the descriptive words (the skill path); pair with --sticky
#   --sticky         remember --words on the window, keyed to the current ticket, so the
#                    plain hook path reuses them until the ticket (branch) changes
#   --dry-run        print "service|ticket|words|name" and rename nothing
#
# Directory resolution (which repo the ticket + service come from):
#   1. --dir, if given                          (explicit, wins)
#   2. --repo <name>  →  <base>/<name>, else ~/code/fuse/<name>, else $PWD/<name>
#   3. the pane's cwd, else $PWD
#   If the shell sits in a container dir that isn't itself a repo (e.g. ~/code/fuse), a
#   bare invocation can't know which repo you mean, so it labels with the container name.
#   Pass --repo to get [FUSE-xyz] service — the caller knows the repo; the dir can't.

set -u

dir="" ; repo="" ; pane="${TMUX_PANE:-}" ; words="" ; sticky=0 ; dryrun=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dir)     dir="${2:-}"; shift 2 ;;
    --repo)    repo="${2:-}"; shift 2 ;;
    --pane)    pane="${2:-}"; shift 2 ;;
    --words)   words="${2:-}"; shift 2 ;;
    --sticky)  sticky=1; shift ;;
    --dry-run) dryrun=1; shift ;;
    *)         shift ;;
  esac
done

# Not in tmux and not dry-running → nothing to do.
[ -n "${TMUX:-}" ] || [ "$dryrun" = 1 ] || exit 0

# Base dir: explicit --dir wins, else the pane's cwd, else $PWD.
base="$dir"
if [ -z "$base" ]; then
  if [ -n "${TMUX:-}" ] && [ -n "$pane" ]; then
    base=$(tmux display-message -p -t "$pane" '#{pane_current_path}' 2>/dev/null) || base=""
  fi
  [ -n "$base" ] || base="$PWD"
fi

# --repo names the repo being worked on, resolved under the base container / common roots.
target="$base"
if [ -n "$repo" ]; then
  for cand in "$base/$repo" "$HOME/code/fuse/$repo" "$PWD/$repo"; do
    if [ -e "$cand/.git" ]; then target="$cand"; break; fi
  done
fi

dir="$target"

# service = git repo basename if inside a repo, else the dir's basename.
toplevel=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null) || toplevel=""
if [ -n "$toplevel" ]; then service=$(basename "$toplevel"); else service=$(basename "$dir"); fi

# ticket + branch-derived words from the current branch (e.g. hjf/fuse-952-snap-error-logs).
branch=$(git -C "$dir" branch --show-current 2>/dev/null) || branch=""
ticket="" ; branchwords=""
if [ -n "$branch" ]; then
  t=$(printf '%s' "$branch" | grep -oiE 'fuse-[0-9]+' | head -n1) || t=""
  if [ -n "$t" ]; then
    ticket=$(printf '%s' "$t" | tr '[:lower:]' '[:upper:]')
    branchwords=$(printf '%s' "$branch" | sed -E "s/.*${t}-?//I" | tr '/_-' '   ' | sed -E 's/^ +//; s/ +$//')
  fi
fi

# Resolve the window for sticky storage + the actual rename (skip entirely on dry-run).
win=""
if [ "$dryrun" != 1 ] && [ -n "${TMUX:-}" ]; then
  if [ -z "$pane" ]; then pane=$(tmux display-message -p '#{pane_id}' 2>/dev/null) || pane=""; fi
  win=$(tmux display-message -p -t "${pane:-}" '#{window_id}' 2>/dev/null) || win=""
fi

# Sticky words: the skill stores them on the window, keyed to the ticket. The plain
# hook path reuses them only while the ticket matches; a branch change clears them.
if [ -n "$win" ]; then
  if [ "$sticky" = 1 ] && [ -n "$words" ]; then
    tmux set-option -w -t "$win" @rename_words  "$words"   2>/dev/null || true
    tmux set-option -w -t "$win" @rename_ticket "${ticket:-}" 2>/dev/null || true
  elif [ -z "$words" ]; then
    storedtkt=$(tmux show-options -wv -t "$win" @rename_ticket 2>/dev/null) || storedtkt=""
    if [ -n "$ticket" ] && [ "$storedtkt" = "$ticket" ]; then
      words=$(tmux show-options -wv -t "$win" @rename_words 2>/dev/null) || words=""
    else
      tmux set-option -wu -t "$win" @rename_words  2>/dev/null || true
      tmux set-option -wu -t "$win" @rename_ticket 2>/dev/null || true
    fi
  fi
fi

# Fall back to branch-derived words when none are set/stored.
[ -n "$words" ] || words="$branchwords"

# Compose: "[FUSE-xyz] service — words", dropping the parts that are absent.
name="$service"
[ -n "$ticket" ] && name="[$ticket] $service"
[ -n "$words" ]  && name="$name — $words"

if [ "$dryrun" = 1 ]; then
  printf '%s|%s|%s|%s\n' "$service" "${ticket:-}" "${words:-}" "$name"
  exit 0
fi

# Stop tmux's own automatic-rename from clobbering us, then set the name.
[ -n "$win" ] && tmux set-option -w -t "$win" automatic-rename off 2>/dev/null || true
[ -n "$win" ] && tmux rename-window -t "$win" "$name" 2>/dev/null || true
exit 0
