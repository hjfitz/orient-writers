---
name: sprint-digest
description: "Build the pair of sprint-boundary Slack posts for the bifrost-general channel — a retrospective digest of the sprint that just closed (at-a-glance counts, production reliability, capability delivered, engineering nuggets) and a look-ahead digest of the sprint just started (capability coming, engineering nuggets). Scopes the look-ahead to the new sprint's To Do column only so carried QA work doesn't muddle it, computes every number from live Jira/GitHub/Datadog/incident.io data, and reports withheld or untrustworthy figures to Harry separately rather than publishing them. Use at sprint kickoff, or when the user asks for a sprint digest, sprint wrap-up, sprint kickoff post, sprint retro post, or what's coming this sprint."
---

# Sprint Digest (two posts, team-facing)

Runs at the **sprint boundary** and produces **two Slack messages**:

1. **Retro** — what the sprint that just closed actually delivered, plus how production held up.
2. **Look-ahead** — what capability the new sprint brings, and the engineering detail behind it.

Sits alongside `/morning-digest` (daily ops, private), `/weekly-digest` (personal retro, private) and `/week-roundup` (Friday team post). This one is **sprint-paced, not calendar-paced**, and the audience is the team plus non-engineers.

Two registers, deliberately separated:
- **The posts are factual** — every line traces to a ticket, PR, metric or incident record gathered below.
- **The caveats are Harry's** — figures that turned out untrustworthy are reported to him in the terminal, never smuggled into the post with a hedge.

---

## Configuration

```
SLACK_CHANNEL   = #bifrost-general (C098LD5PS95)     # ALWAYS. never #bifrost-forge — that's PR announcements
JIRA_CLOUD_ID   = 506e1245-70c1-48d9-aa91-8ae1b7da6eff
JIRA_PROJECT    = FUSE
JIRA_SPRINT_FLD = customfield_10020
GITHUB_ORG      = gfs-bifrost                        # exclude bot authors, but count them
INCIDENT_IO     = https://api.incident.io/v2 — key INCIDENT_IO_API_KEY in ~/.secrets
DATADOG_ENV_TAG = environment:prod | environment:dev  # NOT `env` — see gotchas
ARCHIVE_DIR     = ~/Documents/obsidian/Digests/Sprints/
MAX_CHARS       = 4700 per message                    # 5000 hard limit, footer is auto-appended
```

## Step 1 — Establish the sprint boundary

```
project = FUSE AND sprint in openSprints() ORDER BY key ASC
```
Request `customfield_10020` and read the sprint objects off the issues: each carries `id`, `name`, `state`, `startDate`, `endDate`. The `active` one is the new sprint; **carried issues also list the sprints they came from**, which is how you discover the previous sprint's id and dates without a second lookup.

Record: new sprint name + window, previous sprint name + window.

**Jira results blow the token limit.** Every one of these queries will exceed it. Let the tool write to its result file, then extract with `jq`/`python3` — never try to read the raw response. Probe the shape first (`.issues` is sometimes a bare list, sometimes `.issues.nodes`).

## Step 2 — Gather

### A. The new sprint's real commitment — **To Do column only**

From the openSprints() result, split by `fields.status.statusCategory.name`:
- **To Do** (`Ready for Development`, `Ready for Refinement`) — **this is the look-ahead post's entire scope**
- In Progress / QA states — carried work, *excluded from the look-ahead* (see the scoping rule below)
- `Won't do` — excluded, but count them; breakdown housekeeping is a legitimate nugget
- `Done` — already shipped, excluded

For each To Do item, count its sprint memberships (`[.fields.customfield_10020[].name] | length`). `1` means first time sprinted — genuinely new commitment even if the ticket was written months ago and sat in the backlog. Group by epic (`fields.parent`) and pull the epic bodies for the capability language.

Read the ticket descriptions of the largest epics — the engineering nuggets come from there, not from titles.

### B. The previous sprint's delivery

```
project = FUSE AND status CHANGED TO ("Done", "In QA", "Ready for QA", "Released")
  DURING ("<prev start>", "<prev end +1d>")
```
Epics appearing in this set are the headline — an epic reaching `Ready for QA` is a feature-complete milestone worth its own line. Capture assignees for recognition, and count Done vs reached-QA separately.

### C. GitHub — what merged in the previous sprint

```bash
gh search prs --owner gfs-bifrost --merged --merged-at '<start>..<end>' \
  --json number,title,repository,author,closedAt,url --limit 400
```
Then split bots (`renovate|dependabot|\[bot\]`) from humans, and group by repo and author. Read the **titles** — they carry the engineering nuggets (the bug hunts, the metric fixes, the migrations) that Jira tickets don't.

### D. Incidents

`GET $INCIDENT_IO/incidents`, filter to the sprint window. **incident.io is org-wide** — check the service and the assigned roles before attributing an incident to Fuse. A quiet sprint is a result: "no incidents" is a reliability line, not an empty section.

### E. Datadog — production reliability

Compute for `environment:prod` over the previous sprint window. Read the gotchas below **before** writing any query.

- **API gateway availability** — `fuse.request`, `fuse.request.failure`, `fuse.request.rejected`, `fuse.request.success`
- **Outbound warehouse calls** — `snap_adapter.snap.request.success` / `.failure`, `snap_polling_service.snap.request.success` / `.failure`
- Anything else the sprint's work instrumented

## Step 3 — Compose two drafts

Both posts use the same shape. **The retro gets an At a glance block; the look-ahead does not.**

### Retro

```
*<Sprint N> wrapped* (<start> → <end>). What went out, how prod held up, and some of the engineering behind it.

## 📊 At a glance
- <N> PRs merged — plus <N> automated dependency updates
- <N> tickets completed, <N> more reached QA
- <N> epics reached QA-ready — <names>
- <the sprint's headline block> — <N> tickets across <N> repos
- Zero incidents, zero platform failures in prod        ← only if positively established
- <notable fleet-wide change>

## 📈 Reliability in production
- <availability, with the instrumented scope named>
- <the one real error rate, honestly framed>
- <incidents>

## 🚀 What went out
**<Capability headline in customer terms>**
<What the customer can now see or do that they couldn't. Never enumerate tickets.>

## ⚙️ Engineering nuggets
- **<The interesting technical detail>** — <why it mattered>
```

### Look-ahead

```
*<Sprint N> is underway* (<start> → <end>). Here's what's coming and a few of the more interesting engineering details behind it.

## 🚀 What Fuse gains this sprint
**<Capability headline>** _(<N> tickets)_
<The problem today, then what changes. Customer terms.>

## ⚙️ Engineering nuggets
- **<The nugget>** — <the constraint, the surprise, the deliberate choice>
```

### Section rules

- **🚀 speaks in capabilities, not tickets.** If a bullet can't be phrased as "what can the customer/user do now that they couldn't", it belongs in ⚙️. Lead with the problem as it exists today — "every confirmation is broadcast to every connector" — then what changes.
- **⚙️ is for the genuinely interesting** — a wrong assumption caught, a deliberate design constraint, a silent bug that had been there for ages, a metric that was lying. Not a changelog. The test: would an engineer find it satisfying to read?
- **No delivery-management commentary.** No velocity, no capacity, no ticket-count-versus-time, no "unassigned at kickoff" observations, no sequencing-as-project-management. The team tracks **capability delivery**, not arbitrary times. If sequencing is genuinely interesting engineering (a hard dependency chain), it's a nugget — otherwise it's out.
- **Onboardings are adoption, not product development** — mention as business activity or omit; never a capability headline.
- **No identifiers in the body** — no Jira keys, no repo#num. Non-engineers read this.
- **Recognition is outcome-led and unforced** where it fits, tied to concrete impact. No quotas, no generic praise.

## Step 4 — Approve, post, archive

1. **Print both drafts in the terminal** and iterate until Harry approves.
2. **Report withheld figures separately** — anything computed but not published, and why. This is part of the deliverable, not an afterthought.
3. **Post on approval** to `SLACK_CHANNEL` as **two separate messages** — retro first, then look-ahead. Separate messages so each is independently threadable and reactable.
4. **Check the character count before sending** (`wc -m`). Over ~4700, trim the weakest nugget rather than truncating mid-section.
5. **Archive** to `ARCHIVE_DIR/<sprint>.md`: both final texts, the evidence links, and the withheld-figure notes.

---

## Gotchas

### Scoping the look-ahead

**Use the To Do column only.** The board also carries in-flight and QA work from previous sprints — on a recent run five items had been carried for **three** sprints. Building the look-ahead off the whole board re-announces capability that was already communicated a sprint or two ago (Returns and CSV column ordering both surfaced this way and had to be cut). Carried QA work is not what's coming; it's what already happened and is awaiting sign-off.

**Carried ≠ unfinished dev.** Verify before characterising it: on a recent run every one of the 13 in-flight items had **merged** PRs. The carry was QA verification and customer-paced onboarding, not engineering running late. Check the PRs (`gh search prs --owner gfs-bifrost "<KEY>"`) before implying anything about why something is still open.

**A ticket written months ago can still be new commitment.** Sprint-membership count is the signal, not the created date — Work Order tickets authored in January were sprinted for the first time in Sprint 14.

### Datadog

- **`env` is useless; use `environment`.** Fuse services report `env:serverless` almost universally (`DD_ENV=serverless`), so `{env:prod}` silently matches nothing and returns a bare `null` that reads like zero. The real discriminator is **`environment:prod` / `environment:dev`**.
- **Never compute a percentage from an empty failure series.** An absent series means "no failures recorded", which is either a clean record or a dark metric — and you can't tell which from the query alone.
- **Validate an empty prod failure series against its dev counterpart.** Query `sum:<metric>{*} by {environment}` over the same window: if dev recorded failures and prod produced no group at all, the metric was demonstrably live and prod genuinely had none. That upgrades a weak "none recorded" into a claim worth publishing. Both `fuse.request.failure` and `snap_polling_service.snap.request.failure` behaved exactly this way on a recent run (6 and 18 in dev, nothing in prod).
- **Name the instrumented scope.** `fuse.request` is emitted **only by api-gateway / rest_connector** — it is not platform-wide availability. `fuse.*` instrumentation is still rolling out per-service, so coverage changes sprint to sprint; re-check which services emit before implying breadth.
- **`fuse.request.rejected` is 4xx, `fuse.request.failure` is 5xx** — split mid-2026 so client errors stopped counting as platform errors. `rejected` only began emitting around **10 July 2026**; don't quote a rejection rate spanning that date. Prod rejections have run *higher than accepted request volume*, which is an open question in its own right, not a digest line.
- **`dedupe_service.event.handled` has a step change on 30 June 2026** (~75% down, ~18:00 UTC, flat at the new level since). Any throughput comparison straddling that date is invalid. Cause never attributed — candidates are dual-publish removal, the OMS decommission and the Snap poller ack-deadline/idempotency fixes. Don't publish a trend across it; don't re-derive the drop as news.
- **Skill discovery returns nothing for metrics.** `list_datadog_skills` has no metrics/reliability guide — proceed on tool semantics rather than hunting for one.
- Metrics are `rate` type with a 10s interval — `.as_count()` is required for totals.

### Tooling

- **`gh search prs` has no `mergedAt` JSON field** — it fails with `Unknown JSON field` and, in a pipeline, looks like an empty result. Use `closedAt`. Pass filters as **flags** (`--owner`, `--merged`, `--merged-at`); a bare query string gets mangled into an invalid search.
- **Jira MCP responses always exceed the token limit** for a sprint-sized query. Let them spill to the result file and extract with jq/python. `.issues` may be a bare list rather than `.issues.nodes` — probe first.
- **Slack: 5000 chars per message and a footer is appended.** Target ≤4700. The tool takes standard markdown (`**bold**`) — see [[mcp-slack-markdown-format]].
- **The Slack tools cannot delete or edit.** A misdirected post has to be cleaned up by hand, which is why the channel is fixed in config and never inferred.
