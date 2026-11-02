---
name: orient-record
description: Make sure orient reflects the work done in the current session, recording each thing if and only if it isn't recorded already. Inventories what the session actually did (PRs, monitor/support/incident triage, customer-specific findings, follow-ups owed), checks each against the exact vault record orient builds its pages from, writes only what is missing through the tool that owns that record (wp ledger, cust ledger, the triage record format), updates in place a record this same session wrote that later work made stale, and flags rather than writes anything another skill owns. Trigger when the user asks to update/sync orient for this session, record the session, or make sure orient has what we just did.
---

# orient-record — reflect this session in orient, exactly once

orient (`~/projects/orient`) reads the Obsidian vault in place; it has no write path of its own. So
"orient is up to date for this session" means: every vault record orient derives a page from, for
the work this session did, exists — **once**. Other sessions (another window, a digest, a peer
agent) write the same records, so **check before every write**. A record that already exists is a
success, not a gap.

## Rules

1. **Presence is judged by an exact key, never by vibes.** Each record type below has one: a PR
   reference, a `session_id`, a ticket key. Grep for the key; found anywhere → already recorded.
2. **Write through the owning tool.** `wp ledger` for Waypoint ledgers, `cust ledger` for customer
   ledgers, the owning skill's documented format for triage records. Never hand-edit a ledger file.
3. **Update in place, don't duplicate — but only your own records.** If a record carries *this*
   session's `session_id` and later work in the session changed its facts (a fix shipped after it
   said "not done", a Slack post it cites was deleted), correct that record. A record from another
   session that looks wrong is **flagged**, not rewritten.
4. **Record only what the session actually did.** Everything written must trace to something in
   this conversation (a PR URL, a tool result, a log line). No inferred outcomes.
5. **No Slack, no Jira, no orient code or index changes.** This skill writes vault files only.

## Step 1 — Inventory the session

From the conversation, list every item of these kinds (skip a kind the session didn't touch):

- **PRs opened** — `owner/repo#n`, the repo's Waypoint service name, ticket key or none.
- **Triage runs** — `datadog-triage` (Monitors/), `support-triage` (Support/), `incident-closeout`
  (Incidents/): which alert/customer/incident, and whether a record was written.
- **Customer-specific findings** — a fact about one `businessId`'s setup or history (per the
  Customers-layer rule in the global CLAUDE.md).
- **Ad-hoc task** — the session's work if it left no other record (see the table).
- **Follow-ups owed** — anything left open that Harry should see tomorrow.
- **Skill-owned run logs** — `renovate-clear` / `nightly-clear` / `distraction-duty-digest` write
  their own `Digests/Distraction-Duty/` run log. Note them; they're not this skill's to write.

Get the session id once: `echo $CLAUDE_CODE_SESSION_ID`.

## Step 2 — Check, then write only what's missing

| Item | Where orient reads it | Presence check (the key) | If missing |
| --- | --- | --- | --- |
| PR | `Engineering/<service>/ledger.md` → `/tickets` (ticketed or Out-of-ticket) | `grep -F "owner/repo#n" ~/Documents/obsidian/Engineering/*/ledger.md` — the PR cited in **any** entry counts, even a combined one another session wrote | `wp ledger <service> [--ticket FUSE-n] --title … --body "…\n\nPR: owner/repo#n"` — one entry per repo; no `--ticket` for out-of-ticket work, never borrow an unrelated key; `--force` only for a genuine second same-heading entry the same day |
| Monitor triage | `Monitors/*.md` → `/health` (Triage history) | `grep -l "session_id: <id>" ~/Documents/obsidian/Monitors/*.md`, then match the `monitor:` line | write it in `datadog-triage` Step 7's exact frontmatter + sections, with `session_id` set |
| Ad-hoc task | `Tasks/*.md` → `/tasks` | `grep -l "session_id: <id>" ~/Documents/obsidian/Tasks/*.md` | only when the session produced no PR/ledger entry, triage record or run log: write `Tasks/<date>-<slug>.md` per the global CLAUDE.md "Recording ad-hoc tasks" format |
| Support triage | `Support/*.md` → `/support` | same `session_id` grep in `Support/`, then match business + thread | write it in `support-triage`'s record format |
| Incident | `Incidents/*.md` → `/incidents` | grep the incident.io reference | **flag** — `incident-closeout` owns this record; don't hand-write it |
| Customer finding | `Customers/<BID>/ledger.md` → customer pages | `cust locate <BID>`; if onboarded, grep its ledger for the ticket/PR key | onboarded → `cust ledger <BID> …`; **not onboarded → flag** (`customer-onboard` is its own interactive skill; don't create the folder) |
| Follow-ups | latest `Digests/<YYYY-MM>/<date>.md` `## ✅ Todo` → carried by `morning-digest` | grep the note's Todo for the ticket/PR key | add **one** top-level `- [ ]` item with each follow-up as a sub-item, matching that note's style; `[x]` for sub-items already done |

A new Waypoint folder, customer folder, plan tick, or explainer is out of scope — flag it if the
session implies one is owed, don't create it.

## Step 3 — Correct this session's stale records

For each record from Step 2 carrying **this** `session_id`, compare it against where the session
ended up. Typical drift: the record says a fix wasn't applied but a later PR applied it; it cites a
Slack reply that was since deleted; the outcome or `ticket:` field changed. Edit those fields/lines
in place — keep the record's structure and don't pad it. Leave records from other sessions alone.

## Step 4 — Confirm orient will pick it up

The index follows the vault on its own (`orient-index.service`). Don't rebuild. Just report:

```bash
cd ~/projects/orient && pnpm -s index:status; echo "exit $?"   # 0 healthy · 1 watcher down · 2 empty
```

## Step 5 — Report

One table, one row per inventoried item: **item · status** (`already recorded` / `recorded` /
`updated` / `flagged`) **· where** (file path or the owning skill). Then any gaps orient can't see:

- **Ticket cost attribution.** orient ties a session's token cost to a ticket only when a ticket
  key appears in a slash command's own arguments, or via a `wp tick` on that ticket's plan. If the
  session did ticketed work without either, say that its cost won't show on that ticket's cost
  line — a vault record can't fix it. (Triage records still carry cost via their own `session_id`.)
- **Out-of-ticket and programme cost** comes from `work-usage.jsonl`, which `wp ledger` and
  `wp programme tick` append to with the session id. An entry written with either is priced; a
  ledger entry for programme work written without `--programme`, in a session that never ticked a
  unit, prices on `/ledger` but not on the programme's row. Say so if that happened.
