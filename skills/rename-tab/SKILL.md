---
name: rename-tab
description: Rename the current tmux window/tab to "[FUSE-xyz] service — words". Use when the user asks to rename the tab/window, or proactively when the focus of the work has clearly shifted (new ticket, new service, new sub-task). Sets a short human label describing what's being worked on; the ticket and service are derived automatically from the git branch and repo.
---

# Rename tmux tab

Set the current tmux window's name to `[FUSE-xyz] service — words`, where the ticket
and service come from the git branch + repo automatically and **you** supply the few
descriptive words.

## When to run

- The user asks to rename the tab/window.
- The work focus has clearly moved on — a different ticket, a different service, or a
  distinct sub-task within the same ticket — and the tab no longer reflects it.

Don't spam it. One rename when the context shifts, not after every message.

## How

1. Decide the **words** — 2–5 lowercase words for what's being worked on *right now*
   (e.g. `tracing release-topic dupes`, `fixing CI on the audit job`, `reviewing #156`).
   - Describe the activity, not the ticket or service — the script prefixes those.
   - If nothing is more informative than the branch name, run with no `--words` and let
     the branch suffix supply them.
2. Point it at the repo you're working in with `--repo <name>`, and pass your words sticky:

   ```bash
   ~/.claude/skills/rename-tab/rename-tab.sh --repo <repo> --words "<your words>" --sticky
   ```

   **`--repo` matters** — the shell is usually parked in a container dir (`~/code/fuse`),
   not inside the repo. Without it the label collapses to `fuse` with no ticket. `--repo`
   resolves `<name>` under that dir (or `~/code/fuse/<name>`) and reads *its* branch for the
   `[FUSE-xyz]` ticket + `service`, so a session spanning several repos stays greppable.
   **You** know which repo the work is in — the shell's location can't tell. Omit `--repo`
   only when the shell genuinely is inside the target repo.

   To preview without renaming, add `--dry-run` (prints `service|ticket|words|name`).

3. Tell the user the new tab name in one line.

## Notes

- The script derives `service` from the repo (git top-level basename) and `[FUSE-xyz]`
  from the current branch (e.g. `hjf/fuse-952-snap-error-logs` → `FUSE-952`). On a
  non-FUSE branch it just uses the service name; outside a repo, the directory name.
- **Directory resolution:** `--dir <dir>` (explicit) → `--repo <name>` (resolved under the
  pane dir / `~/code/fuse`) → the pane's cwd → `$PWD`. `--repo` is the one to reach for from
  a container dir; `--dir` is the lower-level escape hatch.
- It targets the window of the pane it runs in (`$TMUX_PANE`), i.e. the one Claude is in.
- `--sticky` stores your words on the window keyed to the ticket. The Stop hook reuses
  them on later turns and **won't clobber them** — until the branch's ticket changes,
  at which point they're dropped and the label reverts to branch-derived.
- It turns off tmux `automatic-rename` for the window so the name persists.
