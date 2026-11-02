---
name: waypoint-work
description: Execute an existing Waypoint plan incrementally — orient from the plan, inspect source narrowly, implement in coherent increments (recording the commit sha on each one ticked), ship them through the same test/commit/deploy/evidence/PR stages as action-ticket, keep the plan current, and perform the completion sign-off (reconcile plan against the real diff, gate on verification and review, append the work ledger entry, create or update explainers). With no ticket given, offers the most recent outstanding plans to pick from instead of requiring one up front. Trigger when the user asks to work on / continue / pick up a waypoint or a planned ticket, or asks to finish, complete, sign off or wrap up the current waypoint. Sign-off runs when the user asks for it, or when Step 1 finds the plan's PR already merged.
---

# Waypoint — work

The primary lifecycle skill. `WP = python3 ~/.claude/waypoint/wp.py`

## Step 0 — Ticket given?

- **A ticket was given** (e.g. `/waypoint-work FUSE-1056`) — proceed to Step 1.
- **No ticket given** (bare invocation) — resolve one before continuing:
  1. `WP fleet` (whole vault) — every open plan grouped by whose turn it is, with real PR
     state. **YOUR TURN is the bucket to offer from**: those are the ones that cannot move
     without the user.
  2. If YOUR TURN is empty, fall back to AN AGENT'S TURN — work that can proceed right now.
  3. Take the top 4 — `AskUserQuestion` caps a single question at 4 options. If more than 4 are
     outstanding, say so when you report back (e.g. "4 of 7 outstanding shown") rather than
     silently dropping the rest.
  4. **Zero outstanding** — say so plainly and stop. Don't call `AskUserQuestion` with nothing
     to offer.
  5. **Exactly one outstanding** — there's no real choice to present (the tool needs at least 2
     options). State which one it is and proceed straight into Step 1 with it, rather than
     opening a one-item modal.
  6. **Two to four outstanding** — call `AskUserQuestion` with one question, one option per
     plan: label `<ticket> — <service>`, description the plan title plus its status and
     last-updated date (e.g. `"Resolve confirmation webhook target by connectorId — active,
     updated 2026-09-01"`). Once the user picks one, treat its ticket as if it had been passed
     as the argument and continue at Step 1.

## Step 1 — Orient from the plan

**`WP brief`** first — from inside the worktree it takes no arguments at all, resolving the service
from cwd and the plan from `worktree:`. One screen, every fact derived live: increments done, the
next one verbatim, branch ahead/behind, uncommitted paths, real PR state with failing checks and
unresolved threads, whether dev is still held by this branch, and whose turn it is. Nothing in it
is stored, so nothing in it can be stale.

The brief is the orientation. Read the plan file itself (`WP context <service> --plan <stem>`, or
just open it) only when you need the *reasoning* — intent, boundaries, assumptions, decisions —
not to work out where things stand.

Two things the brief tells you that change what you do next:

- **PR already merged?** The brief says so, and `YOUR TURN` will read *owed a sign-off*. Skip
  straight to Step 5 — this plan wants closing, not more work. (If `pr:` was never recorded, the
  brief discovers it from the branch; record it with
  `WP plan set-status <service> --plan <stem> --status <current> --pr <n>`.)
- **Anything else wrong with this service?** `WP doctor <service> --no-fetch` — a stale doc on a
  boundary you're about to touch, or a bad frontmatter block, is worth knowing before Step 2.
  STALE-DOC now prints the actual commit subjects, so you can tell a boundary move from a
  Renovate bump without opening anything.
- **Right model for the build?** The brief's `MODEL` line carries the tier planning recommended for
  *implementing* this plan. Check it against the model you're on per
  `~/.claude/waypoint/model-routing.md`: **if you're under the recommended tier, halt before Step 2**
  and `AskUserQuestion` — switch model now / proceed anyway / adjust it
  (`WP plan set-model <service> --plan <stem> --model … --effort …`). Over-powered is a one-line note;
  effort is advice, not a gate. No `MODEL` line (an older plan) → size it yourself from the plan and
  record it with `set-model` so the next session inherits it.

Then work. Don't re-narrate the brief back at the user in prose — it is already on their screen.

If `onboarded: NO`, ask whether to onboard (`waypoint-onboard`) before continuing — offer it,
don't force it. If there's no plan, offer `waypoint-plan`; for a genuinely trivial change,
proceed and say you're working without a plan.

Load nothing else until a specific need names it. Never read the whole ledger, another
service's folder, or the onboarding checklists.

If the plan has a real `ticket:` and it isn't already in progress, apply whichever Jira
transition reads like "In Progress" (`mcp__Atlassian__getTransitionsForJiraIssue`, match by
name) — same convention as `action-ticket`'s Step 0.10. Skip silently for a `ticket: none` plan.

## Step 2 — Execute increments

For each unchecked increment, in order:

1. Inspect only the paths it touches. Read hunks, not whole trees.
2. Implement it. Follow the repo's conventions (`CLAUDE.md`, surrounding code).
3. Run its named verification. Invoke `waypoint-test` when the increment carries real risk
   (a boundary, a contract, a failure path) rather than self-certifying.
4. Tick it with `WP tick <service> --plan <stem> --increment <id> [--note "<what was verified>"]`,
   which stamps the commit from HEAD in the plan's worktree. **Don't hand-write the stamp** — the
   strict `— done: <sha>` format is what four of seven eligible plans got wrong, and `wp signoff`
   reconciles those shas against the real diff (a sha not in the branch is a blocker, a ticked
   increment with no sha is a note). If you commit once in Step 3 rather than per increment, come
   back and `WP tick` each increment that commit closed.
5. **Finish by running `WP brief`, and leave its output as the last thing in the terminal.** Don't
   summarise it in prose above or below — the block *is* the summary. It is what the next session,
   or you tabbing back into this window hours later, reads to pick the work up.

Discipline:

- **Source wins over the plan.** When they disagree, correct the plan in the same increment
  and record it under `Decisions & deviations`. Never work around a wrong plan silently.
- **Guardrails are pushed, not looked up.** Run `WP context <service> --paths <the paths this
  increment touches>` before writing code: it prints only the guardrails tagged to those paths,
  at the top, above everything else. A guardrail is a constraint someone has already been burned
  by — treat one that fires as a stop, not a note.
- **Two attempts, then stop.** If a fix for the same increment fails twice, stop rather than
  trying a third: write a handback (`WP handback --stopped "..." --turn me`) and report. A
  session looping on one increment from 11am to 4pm is what a six-instance day produces, and
  nobody is watching this window.
- **Record a decision when you make one** — `WP decide --text "<what and why>"` prepends a dated
  line to `## Decisions & deviations` and stamps `updated:`, which is what stops a plan worked
  hard all day from looking untouched. Something you would defend in a review six months out is
  a durable record instead: `WP decide --record --title "<the decision, as a claim>"`.
- **Superseding a statement in the plan**: one blockquote immediately *above* the stale text
  (`> SUPERSEDED <date> — <what changed>`), never strikethrough, never a correction buried
  inside it. Six different markers grew in one plan in ten days; this is the one.
- **Poke before a risky increment.** If it touches a path `known-context.md` flags as fragile,
  or a boundary an explainer describes, open that reference in full — not its summary — before
  writing code. Don't assume the plan's own pressure-test already caught it; plans go stale
  between writing and execution, and a trivial-looking increment can turn out to sit on exactly
  the boundary the doc warned about.
- **Capture learnings as they happen.** Something true and durable about the service that isn't
  written down anywhere — a gotcha, a constraint, a fragile edge — goes into the plan's
  `## Learnings` section the moment you find it, not reconstructed from memory at sign-off.
- Genuine product/domain ambiguity is surfaced to the user, not decided by you — **in prose**.
  A modal here would offer your guesses as if they were the candidate answers; ask the open
  question instead.
- No process narration. No pasted diffs or file dumps — `git diff --stat` plus targeted hunks.
- Blocked? You are stopping anyway, so make the stop useful: `AskUserQuestion` — mark the plan
  blocked (with the reason and what unblocks it) / abandon it / carry on with the rest of the
  increments and leave this one unticked. Then `WP plan set-status ... --status blocked --reason
  "<why, and what unblocks it>"` if that is the answer — `--reason` is required for `blocked` and
  `abandoned`, and abandoning prints an unwind checklist derived from real state (a held dev
  environment, an open PR, a worktree, an unmerged branch, shared state git does not own). Work
  through it; don't just read it.
- **A precondition that is not code** — waiting on another ticket to reach prod, on a monitor to
  read real volume — goes on the increment as an indented `gate:` line with a `[ ] confirmed`
  box under it. Sign-off blocks on a ticked increment above an unconfirmed gate, and `WP brief`
  shows unmet gates. Bold prose saying "do not action yet" is not a mechanism; this is.

## Step 3 — Ship the increments

Once every increment you're taking this pass is implemented and ticked, get it to a reviewable
PR. **This is `action-ticket`'s Steps 3-6 — don't re-derive or duplicate its mechanics here.**
Read `~/code/.claude/skills/action-ticket/SKILL.md` for the exact commands, flags and edge cases
(no-PR-flow repos, the screenshot rules) if anything below is unclear. The stages, in order:

1. **Test locally** — full suite, linter, both `build:check` and `build:check:tests`. If there's
   a UI surface, actually drive it in a browser rather than trusting types and unit tests alone.
2. **Commit and push** — `git status` first, stage only the paths this pass touches, a commit
   message that states the *why* and references the ticket, push the branch.
3. **Deploy to dev and verify end-to-end** — invoke `verify`, which deploys the branch
   (the workflow announces it; never post by hand), then actually exercises the change (hit the endpoint,
   publish the event, resolve the config) — "it built" is not evidence.
4. **Capture evidence** — `verify` (Step 3) gathers this as part of driving the flow above;
   write it straight into the plan's `## Verification` section. Invoke `waypoint-test` as well
   here if Step 2 hasn't already covered this ground for a risky increment.
5. **Open the draft PR** — invoke `create-pr` directly, as a draft. Record it on the plan:
   `WP plan set-status <service> --plan <id> --status active --pr <n>`. Post the link, run
   `WP brief` as the last thing in the terminal, and stop — same gate as `action-ticket`: never
   mark it ready without an explicit go-ahead in this conversation.

If the plan already has a `pr:` recorded, skip straight to 1-4 and push to the existing branch —
the open PR picks it up; don't open a second one.

No-PR-flow repos (`ilg-secure-notes`, data-only commits to `fuse-mcp-server`) skip straight from
step 2 to a live smoke test — no dev deploy, no PR, per the exception in `agents.md`.

Config-only work (prod config sweeps, deploy sequencing — no code diff at all) skips this step
entirely. The plan must carry `branch: none` / `worktree: none` (`WP plan new … --config-only`,
or edit the frontmatter) so `wp signoff` gates it on Verification, increments and acceptance
criteria instead of demanding a diff.

Red at any stage sends you back to Step 2 — fix it, retest, don't carry a known-broken change
forward.

## Step 4 — Ship it (only once the user says so)

1. `gh pr ready <url>`.
2. Post the `#bifrost-forge` Slack notification using `create-pr`'s format — it didn't fire at
   draft time.
3. Apply whichever Jira transition reads like "Code Review" (same matching convention as
   Step 1).

If the user asks for changes instead of shipping, make them on the same branch, push, and let
the existing PR pick them up — don't restart Step 3.

## Step 5 — Sign-off

**Triggers:** the user says finish / complete / sign off / wrap up — or a PR merge succeeds,
in which case sign-off runs in the same turn, unprompted.

```
WP signoff <service> --plan <ticket>
```

It reports the *real* facts and exits **2 when BLOCKED**, 0 when PASS:

- diff vs base and changed files; uncommitted work (skipped in **config-only mode**, entered
  when `branch: none`);
- **unchecked increments** and **unmet acceptance criteria** — reported separately, both gate;
  an unchecked box anywhere else is only a note;
- unfilled template placeholders (TS generics and emails are not counted — only template prose);
- a substantive `## Verification` section; any unpromoted `## Learnings`;
- an **increments ↔ commits** table from the `done: <sha>` stamps — a sha not in the branch is a
  blocker, a ticked increment with no sha is a note;
- the PR — from `pr:`, or **discovered from the branch** if `pr:` is empty (record it when it
  says so) — with failing checks, unresolved review threads, CHANGES_REQUESTED as blockers, and
  a note when it isn't merged yet (sign-off before merge is allowed; say so plainly).

**If BLOCKED, do not mark complete.** Report the blockers, then — since you are stopped anyway —
`AskUserQuestion`: fix the blockers now / record the plan as blocked and stop / leave it active and
come back. Never offer "mark complete anyway" as an option; the gate exists to be respected.

If PASS:

1. **Reconcile** the plan against the actual diff — the plan must describe what was really
   done, including anything the diff shows that the plan never mentioned.
2. `WP plan set-status <service> --plan <id> --status complete --pr <n>`.
3. **Ledger** — `WP ledger <service> --ticket FUSE-123 --title "..." --body "..."`.
   Agent-facing: what happened, plus the context a future agent needs (why it was done that
   way, a gotcha, the paths that matter, the PR, `[[explainer]]` links). Terse — a handful of
   lines. Not a diary, not release notes, not a diff summary, not a copy of the plan.
4. **Explainers** — human-facing current system truth. Invoke the `explain` skill with
   `--system <service>`, and `--update <slug>` when `WP context` already listed one covering
   this ground. **Update before you create.** Write mechanism, not history: "requests establish
   a correlation ID which propagates through context and Pub/Sub attributes" — never
   "FUSE-123 added correlation IDs". Skip entirely if the change taught a human nothing new.
5. **Durable docs** — start from the plan's `## Learnings` section (`wp signoff` prints it if
   non-empty): promote each confirmed one into the matching doc, then clear it from the plan.
   A **refuted** learning is not deleted — move it into `## Handback` (`WP handback --tried
   "..."`), because "we tried this and it doesn't work" is exactly what the next person needs
   and the only place it would otherwise have lived is the section sign-off empties.
   A constraint someone could plausibly undo on their own judgement is promoted further, into
   `architecture.md`'s `## Guardrails` list (max ~6, typed and path-tagged) so it is pushed at
   the next agent rather than waiting to be read.
   Beyond Learnings, also edit a doc if the change materially moved a boundary, interface or
   operational behaviour that Learnings didn't already capture. Edit the existing doc; never
   add a new one. Re-anchor what you touched: `WP verify <service> <doc> --paths ...`.
   Then `WP index`.
6. If a cross-cutting scar emerged that outlives this ticket, promote it into
   `known-context.md` rather than leaving it buried in a ledger entry. If the fact is a **dated
   snapshot of mutable state** rather than durable truth ("no PR opened yet", "deploys parked
   since ..."), mark it `(snapshot <date>)` — that doc is exempt from commit staleness by
   design, so an expiring claim inside it otherwise rots invisibly behind what reads as a
   guarantee. `wp doctor` ages marked claims.
7. **Fuse MCP data files.** If `## Affected boundaries` names a topic, endpoint, canonical type,
   MongoDB collection, inter-service dependency or shared package, say so and name the JSON file
   in `fuse-mcp-server/data/` that needs updating (`~/code/CLAUDE.md`, *Maintaining the MCP
   Server*). Waypoint never writes into a repo — flag it; the human or the next agent commits.

Either way — PASS or BLOCKED — **close the turn with `WP brief`** so the terminal's last line says
where this plan now stands and whose turn it is. On a BLOCKED verdict that is the fastest thing to
read; on a PASS it is the receipt.

Abandoned work is marked `--status abandoned --reason "<why>"` and kept — `wp` now requires the
reason, for `blocked` too. Don't delete it.

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

- Verification incomplete, review unresolved, or increments unchecked → stays `active`.
- The plan turns out to be the wrong shape entirely → stop, say so, re-plan.
- A merged PR whose plan can't be reconciled with the diff → report the mismatch rather than
  writing a ledger entry you can't defend.
- Local tests, the dev deploy, or the e2e check go red in Step 3 → fix and retest before
  continuing; never hand off or open a PR on a known-broken change (same rule as `action-ticket`).
