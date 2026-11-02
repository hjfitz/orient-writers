---
name: waypoint-refresh
description: Bring a service's durable Waypoint docs back in line with source after they've drifted — read the commits since each doc's anchor, correct the doc to present-tense truth, then re-anchor it. Handles one service or sweeps every stale service in the vault, fanning out one agent per service. This is the maintenance path for docs that no sign-off will ever cover. Trigger when the user asks to refresh/update/sweep stale docs, when `wp doctor` reports STALE-DOC / ORPHAN-ANCHOR / NO-ANCHOR, or when a service's docs are known to be behind.
---

# Waypoint — refresh

`WP = python3 ~/.claude/waypoint/wp.py`

Sign-off is the normal way a durable doc gets updated, but it only fires when a plan completes —
and most onboarded services have never had a plan. Their docs can only rot. This is the path for
those: **the one skill allowed to write durable docs outside sign-off.**

It is still narrow. Refresh corrects what drifted. It does not redesign a doc, and it never writes
a ledger entry — the ledger records work shipped, not documentation maintenance.

## Step 0 — Scope

```
WP doctor [<service>] --json
```

Take the work from three sections, which need different treatment:

- **STALE-DOC** — commits landed on the doc's `verified_paths` since its anchor. Real work: the
  commits have to be read and the doc corrected.
- **ORPHAN-ANCHOR** — the anchor isn't on the default branch (a pre-squash or rebased commit), so
  the drift count is meaningless. Usually the doc is fine and only needs re-anchoring, but read it
  before assuming that: the real drift is unmeasured, not zero.
- **NO-ANCHOR** — no usable `verified_sha`, or paths that don't resolve. Pick real
  `verified_paths` and anchor. If the repo itself won't resolve, the fix is a `repo:` line in
  `waypoint.yaml`, not an anchor.

Report the scope back before starting — services, doc count, and roughly how much drift. A sweep
of fifteen services is a big operation, so this is a stop worth making: `AskUserQuestion` with the
real options — sweep everything / just the worst-drifted service / re-anchor only (skip the doc
reading) / cancel. For a single service already named by the user, there is no decision to make:
say the scope and go.

## Step 1 — Fan out, one agent per service

Never one agent per doc: a service's docs overlap heavily and one agent reading the commits once
is both cheaper and more coherent. Group the small ones (1–2 commits of drift) several services to
an agent; give a service with heavy drift its own. Launch them **in parallel, in one message**, and
cap it around six at a time.

Each agent's brief must carry, explicitly:

- The vault folder and **exactly which docs to update**, each with its anchor sha, its
  `verified_paths` and its commit count.
- **One exception to the list below**: `waypoint.yaml`'s `runtime:`/`commands:` block and its
  `commands_verified_*` anchor **may** be re-verified against the manifest files it names
  (`wp verify <service> commands --paths ...`, which refuses anything that isn't a manifest).
  That block is the only part of the yaml refresh may write — and without this exception it
  would be the vault's only anchored artifact with no maintainer, which is the exact failure
  this skill exists to close.
- **Do not touch**: `known-context.md` (human knowledge, exempt from staleness), `ledger.md`,
  `waypoint.yaml`, `plans/`, `explainers/`, and the frontmatter fields
  `verified`/`verified_sha`/`verified_paths` — those are re-anchored centrally in Step 2.
- The repo path and its **default branch**, plus: **read-only** — never edit, `git switch`,
  `git stash` or commit; read from `origin/<default>` (`git show origin/main:<path>`) rather than
  the working tree, which is often behind and sometimes dirty. Say how many uncommitted files the
  checkout has so the agent leaves them alone.
- **Do not run `wp.py`** — concurrent frontmatter writes race, and premature re-anchoring hides
  drift the orchestrator hasn't checked yet.
- Any in-flight programme the service is part of (a migration, a rewrite) as something to
  **verify, not assume** — a half-finished migration is exactly the fact a future reader needs
  stated precisely.
- The method: read the doc in full first, then `git log --oneline <anchor>..origin/<default> --
  <paths>`, then `git show --stat` plus the hunks that matter. Correct or delete what the commits
  made false; add what genuinely changed. Keep the doc's existing structure, tone and length
  discipline — no padding, no restating source, point at paths.
- **"Still accurate, no change needed" is a valid result.** A Renovate bump or a formatting pass
  usually touches nothing a doc asserts. Say so and change nothing rather than inventing an edit.
- Genuine "why" gaps get a one-line `UNRESOLVED:` note, never a guess.
- **Docs in the explainer shape keep their blocks true.** If `overview.md` or `architecture.md` opens with an
  `orient-bluf` block, a correction that changes the conclusion updates the BLUF, `thesis:` and `confidence:`
  together (they must match; `node ~/.claude/skills/explain/lint-explainer.mjs <doc>` checks it). A changed
  topology edits the `orient-flow` node or edge, and a re-read claim re-cites its `orient-evidence` row at the
  new sha. Shapes are in `~/.claude/skills/waypoint-onboard/doc-shapes.md`. A doc still in the old prose
  shape stays that way: refresh does not restyle.

Require back, per doc: what changed (or why nothing did), the `verified_paths` to re-anchor with
(each confirmed to exist at the default branch), and any UNRESOLVED items or repo-side problems
noticed but not fixed.

## Step 2 — Re-anchor centrally

The orchestrator does this, never the agents — one writer, no races, and every anchor gets looked
at:

```
WP verify <service> <doc> --paths a,b,c
```

**Widen the paths when the agent asks for it.** An anchor whose paths can't see the change that
matters goes stale invisibly — `fuse-mcp`'s `overview.md` asserted the Go rewrite was mid-flight
while the fact that settled it lived in `iac/env/prod.tfvars`, outside its anchors, so nothing ever
flagged it. If a doc now makes claims about a file its anchors don't cover, add that file.

Then confirm: `WP stale <service>` should be clean (exit 0).

## Step 3 — Report

Per service: docs changed, docs left alone, paths widened. Then the things worth a human's
attention, which are usually the most valuable output of a sweep:

- **Repo-side problems** the agents found and correctly did not fix — a stale code comment, a
  config claim contradicted by its own file, a version mismatch. List them; don't act on them.
- **UNRESOLVED notes** now sitting in docs.
- Anything that turned out **not to be drift at all** — an anchor bug, a wrong default branch, a
  doc that was already right. Those are worth saying out loud because they mean the detector, not
  the doc, needed fixing.

Finish with `WP doctor` to show the sections actually cleared.

## Rules

- **Refresh writes docs; it does not write history.** No ledger entry, no plan status change, no
  explainer creation. If the refresh reveals something durable and cross-cutting, say so and let
  the user decide — promoting it into `known-context.md` is a deliberate act, not a side effect.
- **`known-context.md` is never touched here.** It holds interview truth that doesn't rot on
  commits, and it is exempt from anchors by design. If it has genuinely gone wrong, that's a
  conversation, not a sweep.
- Nothing in a code repo is modified. Ever. Read-only, and read from the default branch.
- Don't refresh a doc for a service with an active plan mid-flight without saying so — that plan's
  sign-off may be about to rewrite the same doc.

## Asking for input

A modal is a **blocking stop**, so the rule is not "prefer the modal" — it is *only stop where you
were going to stop anyway*.

1. **A sensible default exists → take it and say so.** Don't stop for something you can decide.
   Mentioning a choice while carrying on beats interrupting for it.
2. **You'd stop anyway and the options are knowable → `AskUserQuestion`.** One click beats a
   typed paragraph. Cap: 4 options per question, 2 minimum, 4 questions per call.
3. **Only the user holds the fact → ask in prose.** If you had to invent an option to reach the
   two-option minimum, you are in this case (or in case 1). Never manufacture plausible answers to
   a domain question — an invented option anchors the answer, and "Other" does not undo that.

## Stop conditions

- `wp doctor` reports nothing in the three sections → say so and stop; don't go looking for work.
- A doc is so far from reality that correcting it is a rewrite → say so and recommend
  `waypoint-onboard`'s refresh path (or a re-onboard) rather than patching it line by line.
- The repo won't resolve for a service (archived checkout, monorepo app, renamed repo) → fix
  `waypoint.yaml`'s `repo:` first; anchoring against the wrong repo is worse than no anchor.
