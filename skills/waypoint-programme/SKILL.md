---
name: waypoint-programme
description: Work a multi-unit Waypoint programme — a large, sequenced effort (a migration, a re-architecture) tracked by a unit ledger in its Obsidian Migration State doc, driven unit by unit. Rehydrates the programme's context from its `Bifrost/<Name>/` docs and `wp programme status`, then plans / actions / modifies / discusses the next unblocked unit. Trigger when the user wants to work on / continue / pick up a programme by name, mentions a programme unit id, or asks what's next on a migration/re-architecture. The generic replacement for the per-programme bespoke skills.
---

# Waypoint — programme

The programme-level counterpart to `waypoint-work`. A programme is a large effort split into **units**,
each a single shippable change (usually one PR). Its durable record is a **row in the unit ledger**, not
a plan file — a unit is promoted to a full plan only when it warrants one. `WP = python3 ~/.claude/waypoint/wp.py`

Every programme lives in one folder, `~/Documents/obsidian/Bifrost/<Name>/`, holding two docs:
- **`Overview.md`** — the narrative and the verdict. Read once, for *why*.
- **`Migration State.md`** — the live source of truth: the `## Unit status` ledger, `## Gates`, `## Risks`,
  `## Decision log`, `## Scar tissue`. Read every time; it is what `wp programme` reads and writes.

The 80% that used to be re-authored in a skill per programme lives here; the 20% that is genuinely
per-programme (unit scheme, cutover mechanism, invariants, scar tissue) lives in that programme's own
State doc, which this skill reads. Do not hardcode a programme's specifics here.

## Step 0 — Rehydrate (do not skip)

Never assume progress — read the ledger. On invocation:

1. **`WP programme status <name>`** — unit counts by state and group, and the next unblocked unit. This
   is the orientation; it reads the ledger live, so nothing in it is stale.
2. **`Bifrost/<Name>/Migration State.md`** — the `## Gates` (a ticked box is a cleared precondition),
   `## Scar tissue` (do-not-change), `## Risks`, and the `## Decision log` (newest first). These carry
   the per-programme judgement `status` can't.
3. **`Bifrost/<Name>/Overview.md`** — only for the *why* (verdict, strategy, cutover mechanism), and only
   if you don't already hold it.
4. **The repo(s)** the programme touches (from `services:` in the State frontmatter) — read each one's
   `CLAUDE.md`, and reconcile the ledger against real git: a unit may have been merged outside the
   programme. Harry co-edits branches live — re-fetch, never rebase/force-push his branches.

Then **confirm the state back in 2-3 lines** — what's merged, what's next, any gate in the way — before
acting. If `wp programme status` finds no ledger, the folder isn't a programme yet: offer
`wp programme new`, or `waypoint-plan` if it's really one ticket.

## Step 1 — Pick the unit

`WP programme next <name>` gives the unblocked units (todo, every dependency merged). Take the first
unless the user named one. Before working it:

- **Check the gates.** A `## Gates` box that isn't ticked and names this unit (or its group) is a stop,
  not a note — the structural version of "do not action yet."
  A gate names what it holds up after "blocks" (`**G1 — title** — blocks C1, C2.`), and that wording
  is what orient's programme page reads to mark those units blocked and keep them out of "next" — so
  `wp programme next` alone is gate-blind: check the gates yourself before picking from its list.
- **Size the model.** Consult `~/.claude/waypoint/model-routing.md`: a semantic/cutover unit is usually
  `opus/high`; a mechanical one `sonnet/low`. If you're under the recommended tier, halt and say so
  before implementing (the under-powered rule).

## The four modes

**1 — Plan the unit.** Produce a Claude Code plan (use `EnterPlanMode`) for *exactly* this unit, grounded
in the State doc's invariants and the real source — respect the gates, cite `file:line`, don't hand-wave.
If the unit is big or risky enough to deserve the full plan machinery (increments, sign-off), **promote it
to a plan**: `WP plan new <service> --programme <name> --unit <id> --title "..."`, then drive it with
`waypoint-work`. Most units don't need that — a ledger row plus a PR is the point.

**2 — Action the unit.** Implement it holding the State doc's invariants and the repo's conventions. This
is `action-ticket`'s ship stages — test locally, commit/push, deploy to dev and verify end-to-end
(`verify`), capture evidence, open a **draft** PR (`create-pr`). Never mark a PR ready without an explicit
go-ahead. Record the PR with `WP ledger <service> --programme "<Name>" …` (the folder name), so orient
prices the session against the programme. Then advance the ledger (mode 3).

**3 — Modify / advance the ledger.** `WP programme tick <name> --unit <id> --status <state> [--pr "#N"]`
sets the unit's glyph (and PR link) and bumps `updated:`. Add a dated `## Decision log` row for anything
you decided, and any durable gotcha to `## Scar tissue` — by editing the State doc directly (prose, not
tick). Glyphs: ⬜ not started · 🟨 in progress · ✅ merged · ⛔ blocked · ⏸ deferred · ❌ dropped ·
🔄 rescoped. Superseding a statement: one `> SUPERSEDED <date> — …` blockquote *above* the stale line,
never a strikethrough or an inline edit.

**4 — Discuss.** A rigorous thinking partner: reason from the State doc + the real code, cite `file:line`,
name the risk. Don't invent progress the ledger doesn't show.

## Rules

- The State doc is the single source of truth for progress; `wp programme status` is how you read it and
  `wp programme tick` how you advance it. Don't keep a second tally in your head or in prose.
- One unit at a time. Two attempts on a unit, then stop and write what you tried into its Notes cell.
- Product/domain ambiguity is surfaced to the user in prose, never guessed. A blocked unit is
  `--status blocked` with the reason in its Notes.
- Don't retire or rewrite a programme's Overview verdict or its Scar tissue casually — those are the
  hard-won 20%. Correct them with a Decision log entry and a `> SUPERSEDED` marker.

## Stop conditions

- The next unit's gate is unmet → stop, say which gate and what clears it.
- A cutover / one-way-door step (a traffic split, a Terraform flag flip, a prod repoint) → confirm with
  the user before flipping; the State doc's `## Scar tissue` / Overview strategy says how it reverts.
- The current model is under the tier the unit needs → halt (model-routing.md).
- The programme spans work that isn't really one programme any more → say so; re-scope in the ledger
  rather than forcing it.
