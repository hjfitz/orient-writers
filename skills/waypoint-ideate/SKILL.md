---
name: waypoint-ideate
description: Generate and curate "what's next" ideas for a service — tech debt, product evolution, and user-suggested — independent of Jira. Dedupes against this service's ideation history, interviews the user for what source can't know, then has the user keep or discard each candidate with a reason. Kept ideas are saved as draft plan stubs ready for waypoint-plan to flesh out later. Trigger when the user asks to brainstorm/ideate next steps, find tech debt, or asks "what should we work on next" for a service.
---

# Waypoint — ideate

Divergent, not convergent. This produces candidates; `waypoint-plan` turns a kept one into
something executable. `WP = python3 ~/.claude/waypoint/wp.py`

## Step 0 — Orient and load history

`WP context <service>`. If `onboarded: NO`, this one genuinely halts — ideating with no durable
context yields a much thinner list, so it is a real decision rather than a note in passing. Two
knowable options, so `AskUserQuestion`: onboard first (`waypoint-onboard`) / go ahead from source
only, accepting a thinner list. Never proceed on a blank picture without asking.
(Contrast `waypoint-plan`/`waypoint-work`, where the same condition is a non-blocking aside —
mention it and carry on. Don't turn those into modals.)

Read the **entire** `ideas-log.md` if `context` reports any (open the file directly — `context`
only prints headers). This is not optional: an idea already discarded must not be re-surfaced
unless something material has changed in that area since (a later commit touching the same
path, a new ticket, a changed constraint). If it's genuinely unchanged, drop it silently —
don't re-litigate a decision the user already made.

## Step 1 — Generate candidates

Aim for **6-12 candidates total** across the three sources below. Don't pad to hit a number,
and don't dump everything you can think of — this is a curated shortlist, not an audit.

**Tech debt** — mine what the repo and vault already say, don't invent:
- `known-context.md`'s `## Unknowns` and any documented gap, footgun, or deliberate asymmetry
- `architecture.md` for explicitly-flagged rough edges (an unpaginated hot path, a stale pin,
  a "known drift" note)
- `WP stale <service>` — a doc behind its own verified paths is itself a signal something
  changed without the doc catching up
- a bounded `grep -rn "TODO\|FIXME\|XXX" <key_paths>` — a handful of hits, not an exhaustive
  sweep of the whole tree

**Product evolution** — where this service could reasonably grow:
- the repo's own README/CLAUDE.md for gaps the team already flagged in prose (e.g. "nothing
  consumes X yet", "Y is not collected")
- for a Fuse service: `mcp__fuse__lookup-service` plus the relevant `fuse://` resource
  (pubsub-topology, service-dependencies, canonical-types) to spot capability parity gaps
  against sibling services doing similar work — a missing record type, an uncollected
  confirmation, an inconsistent pattern one sibling adopted and this one hasn't
- recent `ledger.md` entries — completed work often implies an obvious, un-ticketed next step
- for a non-Fuse repo, skip the MCP lookups and stay repo-local

**User-suggested** — ask directly, once, after you've shown your own findings so it's
additive rather than a blank-page ask. Keep it **prose**: the whole point is what you *didn't*
think of, which by definition can't be offered as options. Ask it as: "here's what I found — what's been on your mind for
this service? Any roadmap intentions, recurring complaints, or things you've been meaning to
get to?" Take what they give verbatim; don't round it into your own words if it changes the
meaning.

## Step 2 — Present, then keep/discard

Show the full candidate list at once, grouped by source, each as a one-line title plus a
1-2 sentence rationale. Then get an explicit keep/discard decision on **every** candidate —
silence is never a decision:

- Use `AskUserQuestion` in batches of ≤4 (multiSelect, options = idea titles+rationale) for
  the actual keep/discard call.
- For anything not kept, capture a real one-line reason. Ask for it directly if not already
  given — and since those reasons are a knowable set, ask them as an `AskUserQuestion`
  (not valuable / not now / already covered elsewhere / something else) rather than as prose.
  Only fall back to a generic
  "not prioritized right now" if the user explicitly declines to elaborate — never invent a
  more specific reason than they gave you.
- The user may also keep something with modification (narrower scope, different angle) —
  record the idea as they actually left it, not your original pitch.

## Step 3 — Save the decisions

For every candidate, regardless of outcome:

```
WP idea <service> --title "..." --status kept|discarded --source techdebt|evolution|user --reason "..."
```

This is the durable dedup record for future ideate runs — log discards too, not just keeps.

For each **kept** idea, additionally create a stub plan so it's something `waypoint-plan` can
pick up later:

```
WP plan new <service> --title "..." --no-git
```

(No `--ticket` — these aren't Jira-driven. `--no-git` because an idea stub has no branch yet;
without it the tool would stamp whatever branch the cwd happens to be on.) Open the created
file and fill in only the
**Intent** section: the idea's rationale, its source tag, and a line noting it originated
from waypoint-ideate on this date. Leave Acceptance criteria / Increments / everything else as
the template placeholders — that's `waypoint-plan`'s job when the user actually picks this up.
Leave `status: draft` as-is. Then re-run the `WP idea` log line for that candidate with
`--plan <the-created-file-stem>` so the log cross-references the stub.

## Step 4 — Report

List what was kept (with its new plan file) and what was discarded (with its reason), in one
short pass. Nothing here is active work — say so plainly, so the user doesn't think anything
has started.

## Rules

- Never write a candidate straight into `plans/` before the user has kept it — draft stubs
  are for *decided* ideas only, not the working list.
- Don't inflate rationale to make an idea sound more urgent than the evidence supports.
- If the repo has no meaningful signal for a whole source category (e.g. a brand-new repo with
  no ledger history), say so and lean harder on the other two rather than fabricating filler.

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

- Not onboarded and the user declines onboarding → proceed from source only, and say the
  candidate list will be thinner for it.
- The user wants to keep everything with no real discard pass → that's fine, but still ask
  the reason question once per batch so silence isn't mistaken for a decision later.
- A "tech debt" candidate turns out to already have an open PR/plan addressing it → don't
  re-surface it as new; point at the existing plan instead.
