---
name: poker-points
description: "Reconcile a completed round of poker planning in #bifrost-forge into Jira Story Points — either the third-party Poker Planner bot's tally messages (folding in thread replies: a voter revising their own number in-thread overrides their bot vote, a new commitment from a non-voter counts, an explicit decline doesn't) or our own /poker-round reaction-voted ticket messages (1️⃣–5️⃣ reactions, votes only — thread replies are discussion, not votes there). Computes the majority value per ticket (ties broken to the highest tied number), flags a wide split rather than silently resolving it, writes Story Points only where the result differs from what's already set, and transitions a ticket sitting in Ready for Refinement to Ready for Development (never touching any other status). Use when Harry says tickets have been pointed / poker-planned in Slack and asks to update the tickets, sync story points, close out a poker round, or reconcile pointing."
---

# Poker Points

Turns a completed round of poker planning in `#bifrost-forge` into Jira Story Points. Handles
**two distinct message shapes** that can both appear in the channel — tell them apart before
tallying anything, since their voting rules differ:

| Source | How to recognise it | Where votes live |
|---|---|---|
| **Poker Planner bot** (third-party Slack app) | Posted by `Poker Planner`, plain-text `FUSE-NNNN: <title>` (or `[Area] FUSE-NNNN <title>`), ends `Attachment: You are unable to send action` | The bot's own tally line, **plus** thread replies (self-revisions count) |
| **`/poker-round`** (ours) | Posted by us, starts `[FUSE-NNNN](<link>)` | **Reactions only** (1️⃣–5️⃣) — see [[reference_poker_points_skill]]'s sibling doc, `poker-round`. Thread replies there are discussion per the house convention (Confluence "Poker Planning", page 48594965) and are never counted as votes, even a clearly-stated number |

Second of a planned set of poker-planning skills; `poker-round` (kicks off a round) is the other
half. This one only covers **reconciling a completed round into Jira** — it does not request
pointing and does not chase non-voters.

---

## Configuration

```
SLACK_CHANNEL     = #bifrost-forge (C09PBES3MHT)
JIRA_CLOUD_ID     = 506e1245-70c1-48d9-aa91-8ae1b7da6eff
STORY_POINTS_FLD  = customfield_10016
BOT_DISPLAY_NAME  = "Poker Planner"                # bot user id seen 2026-09: U09MFCAQCJC — may
                                                    # rotate on a workspace app reinstall; match on
                                                    # display name first, id as a secondary check
DEFAULT_LOOKBACK  = 7 days                          # unless Harry names specific tickets/a range
TIE_BREAK         = highest tied value              # "use the majority, and if there's a tie, use
                                                    # the highest number" — Harry, 2026-09-10
```

## Step 1 — Find the round's messages

Read `SLACK_CHANNEL` (`mcp__slack__slack_read_channel`) over `DEFAULT_LOOKBACK`, or a narrower
range if Harry named one. **The channel read reliably exceeds the token limit** — let it spill to
the result file and slice/grep rather than loading it raw (same gotcha as `sprint-digest`).

Split what you find into the two shapes from the table above **before** doing anything else —
their vote sources are different and must not be cross-applied. A message from `BOT_DISPLAY_NAME`
goes through Step 2; a message starting `[FUSE-NNNN](` goes through Step 3. Dedupe both by the
`FUSE-\d+` key extracted from the message, not by timestamp proximity — Poker Planner's messages
can land sub-second apart when several tickets are dropped at once, and `poker-round` posts its
whole batch the same way.

## Step 2 — Poker Planner bot messages: tally + thread

Each bot message is one ticket's poll:

```
FUSE-1195: [Snap Poller] Pull stock from Snap, write a JSONL export, and publish a stock_sync confirmation_ready event
Requested by <@...|Fitz>
1 person voted *2* (<@...|Schuster Efigenio>)
3 people voted *3* (<@...|Fitz>, <@...|Nylah Klasson>, <@...|Matt Shaw>)
Average: 2.8
Thread: 1 replies (latest: ...)
```

**Ticket-key position is not fixed** — most messages lead `FUSE-NNNN: [Area] ...`, but at least one
observed instance reads `[Area] FUSE-NNNN ...` instead. Regex `FUSE-\d+` anywhere in the first
line; don't assume a prefix position.

Parse the vote lines into `{ person → number }` — this is the baseline, before any thread
adjustment. For every message whose parent shows `Thread: N replies`, read it
(`mcp__slack__slack_read_thread`, **both** `channel_id` and `message_ts` are required — the call
errors without `message_ts`). Classify each reply against the baseline tally:

| Reply shape | Example seen | Effect |
|---|---|---|
| **Self-revision** — someone already in the bot tally states a new number | Matt Shaw (bot vote *1*) replies "happy to go with a 2 here" on FUSE-1193 | **Overrides** their bot vote with the new number |
| **New commitment** — someone *not* in the bot tally states a number as their assessment | — | **Adds** them to the tally at that number |
| **Explicit decline** — states they aren't voting | Harry Humby: "no vote for me 🥲" on FUSE-1189 | Excluded entirely — not added, and overrides any bot vote they somehow also had |
| **Hedged-but-real estimate** — hypothetical phrasing ("would have voted N", "fwiw") that still names one clear number | Harry Humby: "I would have voted 1 fwiw" on FUSE-1191 | Counted at N — the hedge is about confidence, not withdrawal; a person who wanted to abstain says so explicitly (see the row above) |
| **No clear number** — discussion, a question, a reaction with no stated value | — | Not counted; if it changes how you'd read the result (a raised complexity concern under a low estimate, say), surface it in the report as colour, not as a vote |

The two real self-revision cases seen so far (FUSE-1193, FUSE-1195) both moved a dissenting voter
onto the existing majority — but the rule doesn't assume that direction; a self-revision can just
as easily create a new majority or a new tie.

## Step 3 — `/poker-round` messages: reactions only

Per the house convention this format was built to (Confluence "Poker Planning", page `48594965`,
Bifrost space — "no explanations, no justifications, only emojis... converse in the threads"):
**a `/poker-round` ticket message's vote is its reactions, full stop.** Do not read its thread for
votes, even a reply that states a clean number the way the bot-flow table above would count — a
person voting this way had a reaction available and chose not to use it.

For each such message, call `mcp__slack__slack_get_reactions` (`channel_id` + `message_ts`).
Filter to the five keycap-digit reactions — `one`, `two`, `three`, `four`, `five` — and build
`{ person → number }` from the user lists. Ignore every other reaction name (a 👍 ack, a 🎉, etc.
carries no vote).

**A person reacting with more than one of the five numbers is ambiguous, not resolvable from the
API.** `slack_get_reactions` returns counts + user lists per emoji with no per-reaction ordering,
so there's no way to tell which one is "current." Exclude that person from the ticket's auto-tally
and call it out by name in the Step 6 report — don't guess.

## Step 4 — Compute the result

Per ticket, from whichever source applied: mode of the final `{ person → number }` map. Tie → the
**highest** tied value.

**Flag a wide split rather than silently resolving it** — the source convention (same Confluence
page) originally called for escalating any disagreement to an in-person session; live practice has
instead been to auto-close on majority (FUSE-1189/1194 both closed 2-2 ties without escalation), so
this skill still writes a value either way. But surface it clearly when either holds: the vote span
(`max - min`) is `≥ 3`, or the winning value holds `< 50%` of counted votes. That's Harry's call to
override, not a silent auto-resolution.

## Step 5 — Write only what changed

Fetch each ticket's current `customfield_10016` **and** `status` (`mcp__Atlassian__getJiraIssue`,
fields `["customfield_10016", "status"]`). If the computed value differs (including from `null`),
write it:

```json
{ "fields": { "customfield_10016": <value> } }
```

**Send only this one field.** Never combine it with a `description` edit in the same call —
`editJiraIssue` with a `description` payload has been observed to silently clear `labels` on this
project; an isolated `customfield_10016` write doesn't touch that path, and there's no reason to
risk it.

If the computed value already matches, skip the write — don't generate no-op history on the
ticket.

**Then, separately, transition the ticket to Ready for Development** — pointing is the gate that
moves a ticket out of refinement (Harry, 2026-09-11). Only act when the ticket's `status` is
exactly **Ready for Refinement** (status id `10806`): call `mcp__Atlassian__transitionJiraIssue`
with `transition: { "id": "5" }` — **not** a bare `transitionId` field, which the tool rejects
(`Required at transition`, hit live on the FUSE-1200–1208 round before the fix). Confirmed via
`getTransitionsForJiraIssue` — globally available, lands on status id `10807`, "Ready for
Development". **Do this regardless of whether Step 5's points write actually fired** — a ticket
whose computed value already matched Jira still needs transitioning if it's sitting in Ready for
Refinement.

**Never transition a ticket in any other status.** A ticket already past Ready for Development (In
Progress, Code Review, Ready for QA, In QA, Done, …) is mid-flight work — moving it would regress
or misrepresent real progress, not reflect that it got pointed. A ticket still in Backlog hasn't
been through refinement yet; pointing it in a round doesn't mean refinement happened, so leave its
status alone and say so in the report rather than silently promoting it.

## Step 6 — Report

A compact table, one row per ticket processed, noting which source it came from:

```
FUSE-1193 [bot]    — 1×1, 3×2 → Matt Shaw revised 1→2 in thread → final 2 (unanimous) → Jira: (unset) → 2 → Ready for Development
FUSE-1195 [bot]    — 1×2, 3×3 → Schuster revised 2→3 in thread → final 3 (unanimous) → Jira: (unset) → 3 → Ready for Development
FUSE-1189 [bot]    — 2×1, 2×2 (tied) → tie-break → highest → 2 → Jira: (unset) → 2 → Ready for Development
FUSE-1220 [round]  — 1️⃣×1, 2️⃣×3 → final 2 → Jira: (unset) → 2 → Ready for Development
FUSE-1221 [round]  — 1️⃣×2, 5️⃣×2 (tied, wide split ⚠️) → tie-break → highest → 5 → Jira: (unset) → 5 → Ready for Development
FUSE-1222 [round]  — 2️⃣×3, 3️⃣×2 → final 2 → Jira: 2 → 2 (unchanged) → already Code Review, left alone
```

Call out anything genuinely ambiguous (a hedged estimate you counted, a decline that removed
someone from an otherwise-tied result, a `/poker-round` voter excluded for a multi-number reaction,
a wide-split ⚠️) rather than letting it pass silently — the table should let Harry catch a miscall
without re-deriving the whole thread or reaction list himself. Note every status transition (or the
lack of one, and why) alongside the points result — a silent transition is as bad as a silent
points write.

## Step 7 — Close the round's `Tasks/` record

For a `/poker-round` round, `poker-round` Step 5 left a `Tasks/<date>-poker-round-<slug>.md` with
`status: open`. Find it by grepping `Tasks/` for the tickets' keys (newest match wins). Fill each
row's Points cell with the final value (or `closed, not pointed` / `left, still in Backlog` where
that's what happened), then set `status: done` and update the `tldr` to say the round is
reconciled. If some tickets are still unreconciled, leave it `open` and say which in the tldr. Round
with no matching record (e.g. a Poker Planner bot round): skip, nothing to close.

---

## Gotchas

- **`customfield_10016` is Story Points on this project** — confirmed live by a successful write
  (2026-09-10/11), not by a field-name lookup; no tool surfaced a name→id mapping directly. If a
  future write is rejected as an invalid field, that's the first thing to re-verify — Jira field
  ids aren't guaranteed stable across a project reconfiguration.
- **Bot messages can arrive rapid-fire** (sub-second `Message TS` deltas when Harry drops several
  tickets for pointing at once) — dedupe on the `FUSE-\d+` key extracted from the message, not on
  timestamp proximity.
- **`Average` in the bot's own message is not the value to use.** It's the raw numeric mean
  (e.g. `2.8`), never a valid Fibonacci-style estimate on its own — always compute the mode from
  the individual votes, per Harry's stated rule, not the bot's average.
- **The two source types are told apart by the message's own text** (`Poker Planner` bot text vs.
  our `[FUSE-NNNN](` prefix). Which tickets are in an open round comes from Slack, not the vault:
  a round is whatever matching messages exist in the lookback window, and nothing needs to be
  reconciled the same day it's posted. The `Tasks/` record from `poker-round` is only a
  reminder and an audit trail, never the source of truth for votes.
- **Don't read a `/poker-round` message's thread for votes.** It's tempting to reuse Step 2's
  self-revision logic there too, but the house convention this format follows is explicit that
  thread replies are discussion, not ballots — a stated number in a `/poker-round` thread is colour
  for the report, never a vote.
- Mirrors `sprint-digest`'s Jira/Slack token-limit and thread-parameter gotchas — see that skill
  if extending this one.
- **The Ready for Development transition is `id: "5"`** — confirmed live via
  `getTransitionsForJiraIssue` on FUSE-1196 (2026-09-11), globally available from every status,
  landing on status id `10807`. Only actually *call* it from status id `10806` (Ready for
  Refinement) though — see Step 5's guard. If a future project reconfiguration changes these ids,
  a rejected transition call is the signal to re-verify, same as the `customfield_10016` gotcha
  above.
