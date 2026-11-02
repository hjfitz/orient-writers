---
name: waypoint-status
description: The single read-only entry point into Waypoint. Given a ticket number, find which service's plan tracks it (searching the whole vault) and report its real implementation status — increments done vs outstanding, verification evidence, open questions. Given a service or repo name/path, resolve its vault folder and give a compact orientation — onboarded or not, doc staleness, active plans, recent ledger. Given nothing, list everything outstanding across the vault (ticketed vs non-ticketed) and flag any merged PR whose plan was never signed off. Never writes. Trigger when the user asks about a ticket's status, whether a service has a Waypoint folder or wants orientation on one, what's outstanding/in flight/on the board, or runs this with no argument.
---

# Waypoint — status

Reporting only. No writes, no status changes. `WP = python3 ~/.claude/waypoint/wp.py`

One skill, three modes, chosen by the argument. This is the formalised version of the check
CLAUDE.md asks for before non-trivial work on a service — "does this have a Waypoint folder, and
what does it say" — plus the two questions next to it: "what's happening with this ticket" and
"what's outstanding overall." Reach for this instead of `find`/`grep`-ing the vault by hand.

## Step 0 — Which mode?

- **Ticket** (`<PROJECT>-<number>`, e.g. `FUSE-1056`) → **Mode A**.
- **Service, repo name, or path** (anything else) → **Mode B**.
- **No argument** → **Mode C**.
- Malformed ticket (looks like one but isn't `<PROJECT>-<number>`-shaped) → ask for the real key
  rather than guessing at a search.

## Mode A — one ticket

```
WP find <ticket>
```

Searches every service's `plans/*.md` frontmatter for a matching `ticket:`, case-insensitive,
and prints the plan's **file stem**.

- **No match** — say plainly that it isn't tracked in Waypoint. Don't offer to create a plan;
  that's `waypoint-plan`'s job, only on request.
- **More than one match** (a ticket spanning services) — pull all of them; present each
  service's plan separately rather than picking one.

Then pull the full plan **by the stem `find` printed** (`--plan` matches file stems; a bare
ticket works only because the stem starts with it):

```
WP context <service> --plan <stem>
```

Report from what this returns, not from memory or from Jira — the plan is the source of truth
for *implementation* status; Jira's status field can lag or drift from it in either direction
(FUSE-1050: Jira said "In QA" while the PR was an open draft; FUSE-866: the PR merged and the
plan sat `active` for a day). Cover, in order:

- **Anything still waiting on the user** — an unanswered question on a PR thread or in the
  Decisions log is the single most actionable thing to surface. First, not buried.
- **Status** (`active`/`blocked`/`draft`/`complete`/`abandoned`) and when it last updated.
- **Increments**: checked vs outstanding, and *why* an outstanding one is blocked if the plan
  says so — quote the blocker, don't paraphrase it away.
- **Verification**: what evidence actually exists for the completed increments — this is what
  lets you say something is *done*, not just *coded*.

If `context` shows `pr:` empty but the plan has a branch, the user may believe it merged: run
`gh pr list --head <branch> --state all` in the worktree and say what you find. If it is merged,
that plan is owed a sign-off — say so and point at `waypoint-work <ticket>`; don't run it.

## Mode B — one service

```
WP locate <target>
```

`<target>` is a repo name, a path, or a service name. This tells you the canonical service, the
repo path, the vault path, and whether it's onboarded.

- **Not onboarded** — say so plainly and stop. Don't fabricate a summary from the repo itself;
  that's exactly the context-free proceeding CLAUDE.md exists to prevent. Point at
  `waypoint-onboard`; don't run it unprompted.
- **Onboarded** — `WP context <service>` and present what it returns in its own structure (it's
  organised for scanning, not prose): doc staleness first — flag anything `STALE:` or
  `NO-ANCHOR` prominently, a stale doc is a reason to verify before trusting, not a footnote —
  then explainers, active plans with status, the last few ledger entries.
- If the question is really about one piece of work, add `--plan <stem>` and switch to Mode A's
  reporting.

## Mode C — everything outstanding

```
WP fleet
```

`wp fleet` groups every open plan by **whose turn it is** — YOUR TURN / AN AGENT'S TURN /
WAITING ON A REVIEWER / WAITING ON THE WORLD — computed from real PR state (failing checks,
review decision, unresolved threads, draft, merged-but-unsigned), the increments left, and
whether dev is still held. It prints its own bucketing rules underneath, so a miscall is visibly
wrong rather than quietly believed. `--turn mine` narrows it to what is waiting on the user.

Present the buckets as it prints them; **lead with YOUR TURN**, which is the only one that needs
a decision now. `wp list --check-prs` remains the flat ticketed/non-ticketed view — reach for it
only when the user wants the whole board rather than what needs them.

- Say the total count per list up front ("3 ticketed, 1 non-ticketed").
- Surface every `<<< UNCLOSED WAYPOINT` flag prominently — that is the one finding worth calling
  out unprompted, with the fix: `waypoint-work <ticket>` to run sign-off.
- Surface every `!!` warning too — a plan that *couldn't* be checked is not a plan that's fine.
- If a `blocked` plan's reason isn't obvious from its title, open it (`WP context <service>
  --plan <stem>`) and quote the blocker rather than guessing.
- Don't summarise into prose. A list a person can scan is the deliverable.
- Both lists empty → "nothing outstanding right now"; don't pad.

For a whole-vault health view beyond open work — stale docs, unanchored docs, bad frontmatter,
plans going quiet — that's `WP doctor`, which the morning digest runs daily. Mention it if the
user asks about vault health; don't re-implement it here.

## Rules

- Never change a plan's status, write a ledger entry, touch a doc, onboard, plan, or start work
  from this skill. Hand off to `waypoint-onboard` / `waypoint-plan` / `waypoint-work`.
- Complete/abandoned plans are deliberately excluded from Mode C — it's an outstanding-work view,
  not a history. `WP status <service>` shows everything if the user wants history.
- Don't re-derive what `wp context`/`wp list` already computed by reading raw vault files, unless
  something in their output needs deeper investigation.

## Stop conditions

- No vault at all (`~/Documents/obsidian/Engineering` doesn't exist) — say so; nothing is
  onboarded yet.
- A target that resolves to no known repo and isn't a vault-only service name either — ask for
  the exact repo/service name rather than guessing.
