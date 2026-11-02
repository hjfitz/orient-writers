---
name: poker-round
description: "Kick off a round of Bifrost poker planning in #bifrost-forge using reaction-based voting — a kickoff message explaining the 1-5 scale and how to vote, then one standalone message per ticket (link + title + a human-centric, implementation-detail-free tl;dr) seeded with 1️⃣-5️⃣ reactions so people just click. Follows the house 'Asynchronous Ritual' convention (Confluence: Poker Planning, Bifrost space) rather than the third-party Poker Planner bot, so votes never leak to other voters until someone deliberately tallies them. Pairs with /poker-points, which reconciles the reactions into Jira once voting closes. Use when Harry asks to poker plan / point / start pointing a set of tickets."
---

# Poker Round

Opens a round of poker planning in `#bifrost-forge` using plain reactions instead of the
third-party `Poker Planner` Slack app — built because that app's votes are cast via interactive
buttons the Slack MCP toolset can't click on anyone's behalf, and its native `/pp` command can only
be run by a human typing it. This is the house alternative: the **Asynchronous Ritual** already
documented on Confluence ("Poker Planning", Bifrost space, page `48594965`), automated.

Reactions are visible in real time to anyone who looks — this is **not** a blind ballot the way a
DM-collected vote would be. That trade-off is deliberate (Harry, 2026-09-11): it keeps voting as
low-friction as a click, matching how the team already runs this ritual by hand.

First half of the pair with [[poker-points]] — this skill only opens a round and posts the
ballots; it never tallies or writes to Jira itself.

---

## Configuration

```
SLACK_CHANNEL       = #bifrost-forge (C09PBES3MHT)     # matches where pointing already happens
                                                        # live, not the doc's example #bifrost-planning
JIRA_CLOUD_ID       = 506e1245-70c1-48d9-aa91-8ae1b7da6eff
STORY_POINTS_FLD    = customfield_10016
VOTE_EMOJI          = one, two, three, four, five       # standard Unicode keycap digits — no
                                                        # custom emoji needed or searched for
VOTING_WINDOW        = 24 hours                          # per the Confluence ritual; this skill
                                                        # states the deadline in the kickoff message
                                                        # but does not auto-schedule the reveal —
                                                        # Harry (or a scheduled task) runs
                                                        # /poker-points when voting's done
NOTIFY_GROUP        = <!subteam^S0BGJ8A3NG7>            # the group Harry tagged when kicking off
                                                        # pointing in-session — confirm this is
                                                        # still the right group before reusing blind
SCALE_SOURCE        = Confluence "Poker Planning", page 48594965, Bifrost space
```

## Step 1 — Resolve the ticket set

Harry will name tickets one of two ways — handle both:
- **Explicit keys** ("poker plan FUSE-1220 through FUSE-1225", or a pasted list).
- **A criterion** ("everything in FUSE-967 without points", "the To Do column for Sprint 16") —
  resolve via `searchJiraIssuesUsingJql`, e.g. `parent = FUSE-967 AND "Story Points" is EMPTY`.

**Skip anything that already has `customfield_10016` set**, and say so in the final report, unless
Harry explicitly asked to re-point it — re-running a vote on an already-pointed ticket just adds
noise to the channel and the history.

Fetch each surviving ticket's `summary` and `description` (`getJiraIssue`).

## Step 2 — Write the tl;dr

One sentence per ticket, **free of implementation detail, human-centric** — the same bar the
digest skills hold "🚀" sections to: could someone who doesn't know this codebase read it and
understand what's being asked? Draw from the ticket's Overview/Objective (and Acceptance Criteria
if the Overview alone is too thin), never from its "🤖 Agent reference" section — that section is
implementation detail by the ticket template's own definition.

Cut: file/class/schema/topic names, service internals, canonical type names, specific tech
(`Pub/Sub`, `Zod`, `Terraform`). Keep: what the ticket accomplishes and, briefly, why.

```
❌ Add stockSyncEnabled/stockSyncSchedule to ShopifyIngress + its Zod schema in @gfs-bifrost/types,
   mirroring stockAdjustmentsEnabled/outboundTagsEnabled.

✅ Let a Shopify connector be configured with a stock sync schedule — which days, what time.
```

## Step 3 — Post the kickoff message

One message, once per round, **not** per ticket. The Confluence scale is deliberately played for
laughs there ("Swat the Rat", "Systemic Horror", "Estimation is not a science, it is a seance") —
**don't carry that tone into the channel post itself**; keep the same 5 levels and real time bands,
but write it straight (Harry, 2026-09-11):

```
📋 *Poker Planning* — <NOTIFY_GROUP>

<N> tickets below are up for pointing. React on each with the number matching your estimate. Keep
the vote itself free of commentary — discussion goes in the ticket's thread, not the vote.

1️⃣ ~30min–2hr — a small, contained change (a lint fix, a typo, a one-file tweak)
2️⃣ ~½–1 day — small and well-understood, touches a couple of files
3️⃣ 1–2 days — moderate, some digging into existing code required
4️⃣ 3–5 days — complex, spans multiple services or dependencies
5️⃣ 1+ week — large; consider splitting into smaller tickets

Voting closes in <VOTING_WINDOW>.
```

The Confluence page stays the reference for background/history if anyone asks, but isn't linked
from the post itself — the post should read as a normal team process, not a pointer to the joke.

## Step 4 — Post one message per ticket

Exactly Harry's format:

```
[FUSE-1234](<jira link>) <summary>
*<one-line tl;dr from Step 2>*
```

Immediately after each send, seed all five reactions on it (`mcp__slack__slack_add_reaction`,
once per emoji in `VOTE_EMOJI`) so voters click rather than type shortcodes. This is five extra
tool calls per ticket — accept the cost; it's the whole point of the reaction-vote ergonomics.

## Step 5 — Record the round in `Tasks/`

Write `~/Documents/obsidian/Tasks/<YYYY-MM-DD>-poker-round-<slug>.md` (slug from the epic or theme)
so orient's `/tasks` page shows the round as owed work until it's reconciled. Use the ad-hoc task
format from the global CLAUDE.md with `tags: [adhoc-task, poker-round]`, `status: open`, and the
current `session_id`. The tldr names the ticket range and the voting deadline. The body has a
`## Outcome` line saying `/poker-points` is owed, plus a table of `Ticket | Message | Points`, one
row per posted ticket, each with its Slack permalink
(`https://gfsdeliver-eng.slack.com/archives/C09PBES3MHT/p<ts without the dot>`) and `pending` in
the Points column. Skipped (already-pointed) tickets don't get a row. `/poker-points` closes it.

## Step 6 — Report back

List what was posted (ticket, link, tl;dr used) and what was skipped (already-pointed, with its
existing point value) so Harry can see the round's actual scope without re-reading the channel.

---

## Gotchas

- **Don't reuse `Poker Planner`'s message shape.** `/poker-points` tells the two sources apart by
  matching `[FUSE-NNNN](` as this skill's signature — starting a message any other way (e.g. plain
  `FUSE-NNNN: ...`) makes it indistinguishable from the bot's own posts and breaks reconciliation.
- **Reactions are not blind.** If a genuinely hidden-until-reveal ballot is ever wanted, this isn't
  it — see the DM-collection design discussed and set aside in favour of this one (2026-09-11).
- **`VOTE_EMOJI` names are the Slack shortcode, not the ticket point value's display form** — react
  with `:one:` through `:five:`, which render as 1️⃣–5️⃣; there's no need to search custom emoji
  (`slack_search_emojis` is for workspace-specific ones only — these are always-available Unicode).
- **This skill never writes to Jira.** Even an obviously unanimous-looking reaction set stays
  unreconciled until `/poker-points` runs — don't shortcut the pair.
- **`slack_send_message` takes standard Markdown, not Slack's own `*bold*` mrkdwn** — bold is
  `**text**` (double asterisk), matching [[reference_mcp_slack_markdown]]. Every sample drafted
  earlier in this skill's own history used single-asterisk Slack syntax; the real sends use
  double. Don't copy the single-asterisk form from an old preview into an actual send.
- **Skip already-pointed tickets even mid-range.** A round spanning a ticket range you've named
  can straddle earlier, already-reconciled tickets (e.g. `FUSE-1194-1199` when `1194`/`1195` were
  pointed in an earlier round) — always fetch `customfield_10016` per ticket before posting, don't
  assume a contiguous key range is all unpointed.
