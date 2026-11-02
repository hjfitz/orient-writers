---
name: distraction-duty-digest
description: Run a distraction-duty health-and-hygiene pass — a 24h prod status snapshot from Datadog (incidents, monitor status + flapping history, key metrics), clearing every open Renovate dependency-bump PR into a mergeable green state and merging it (invokes `renovate-clear`), and a nightly-build health check (`nightly-health`) that merges any already-existing fix PRs but never originates a new fix without an explicit go-ahead. Writes a combined report to the Obsidian vault. Trigger when the user asks to run distraction duty, do a distraction-duty pass/digest/sweep, or wants prod status + Renovate PRs + nightly builds handled together.
---

# Distraction Duty Digest

Distraction duty is the team's rotating catch-all for BAU/off-roadmap work — see the current sprint's "[Sprint N] Distraction Duty" ticket ([[reference_fuse952_distraction_duty]] in memory: `FUSE-952` → `FUSE-1000` → `FUSE-1078` → …, rotates every sprint). This skill is the health-and-hygiene pass you run while carrying it: is prod okay, are the dependency PRs clear, are the nightlies green. It is **diagnosis + PR hygiene, not incident response** — if Step 2 turns up something that looks like a live, unresolved incident (not routine noise), say so and hand off to the `incident-response` skill rather than digging further here.

Three phases — **prod status → Renovate → nightlies** — then one combined report to Obsidian. The middle two phases carry deliberately different authorization: Renovate PRs get merged unconditionally per the org's own standing policy (mirrored from `renovate-clear`); nightly-build **fixes** never do — landing an already-existing clean fix PR is fine, but originating a new fix is always Harry's call, not this skill's, and that gate holds even mid-run.

---

## Configuration

```
VAULT        = ~/Documents/obsidian
REPORT_DIR   = ~/Documents/obsidian/Digests/Distraction-Duty   # sibling to Digests/{Sprints,Roundups,Weekly} — same precedent
GITHUB_ORGS  = gfs-bifrost, ilg-platform     # matches renovate-clear's own multi-org sweep
NIGHTLY_ORG  = gfs-bifrost                   # matches nightly-health's default
PROD_WINDOW  = 24h
JIRA_PROJECT = FUSE
```

## Step 1 — Setup

```bash
TODAY=$(date +%F)
NOW_UTC=$(date -u +%H:%M)
mkdir -p ~/Documents/obsidian/Digests/Distraction-Duty
SINCE_24H=$(date -u -d "24 hours ago" +%FT%TZ)
```

Resolve the current distraction-duty ticket (for the report header, not for gating anything): `searchJiraIssuesUsingJql` — `project = FUSE AND summary ~ "Distraction Duty" AND sprint in openSprints()`. No match → note "no active distraction-duty ticket found" and carry on; this is context, not a blocker.

Check whether today's report file already exists (`REPORT_DIR/$TODAY.md`) — if so, this is a second run today; Step 5 **appends** a new `## Run @ HH:MM UTC` section rather than overwriting (never rewrite a past run's section).

---

## Step 2 — Prod status (last 24h)

This is a snapshot, not a re-investigation from scratch every time — check project memory first (`~/.claude/projects/-home-hjf-code-fuse/memory/`) for anything already tracked (a known false-firer, a silently-dead monitor, an open follow-up like a re-announce loop) before treating a firing or flapping monitor as new. Cite the existing memory/ticket instead of re-deriving root cause; only dig fresh when nothing in memory explains it.

**Skill discovery first** — `list_datadog_skills` (query "monitors metrics dashboards health") and load anything clearly matching before querying. There is no `datadog/monitors` skill; don't guess one.

Gather:
- **Incidents** — `search_datadog_incidents` for anything active, or created/resolved in the last 24h. Each with its app URL.
- **Monitor status rollup** — `search_datadog_monitors` scoped to Fuse's monitor tags (`domain:fuse` / `team:fuse` / `team:fuse-developers` / `team:bifrost`, prod). Counts of OK / Warn / Alert / No Data / Muted, plus every non-OK monitor named with a link.
- **Flapping history, not just current state** — a monitor that triggered and recovered five times overnight reads as "OK" in a point-in-time check but is not actually quiet. Pull `search_datadog_events` (`source:alert`, Fuse tags, `from: now-24h`) and group by monitor title into trigger/recover **cycles**, not raw event count. For any monitor that's currently non-OK, or flapped more than a couple of times in the window, pull one level deeper — `get_datadog_metric` grouped by the metric's own tags (e.g. `businessid`, `failure_mode`, `recordtype`) over the window — to name the likely driver rather than just reporting "it flapped N times." This is the same shape of pass as a manual "what's been firing" check; do it at that depth, not shallower.
- **Key metrics snapshot** (24h, prod) — same headline set as the morning digest: records ingested, platform failures (`create_data_failure`), Fuse API availability, worst Pub/Sub backlog. A pulse, not the dashboards.
- **Dashboards** — the curated Fuse dashboard links (see `morning-digest`'s `DATADOG_DASHBOARDS` list) as jump-in references; no need to re-query them.

If everything traces to already-known, already-tracked noise, say that plainly ("all clear — the only non-OK monitor is the known dead one, see below") rather than padding the section.

---

## Step 3 — Renovate PRs (merge unconditionally per policy)

Invoke the **`renovate-clear`** skill (`~/code/.claude/skills/renovate-clear/`) in full — sweep → repair → merge → report — across `GITHUB_ORGS`. Don't reimplement its logic here; it already encodes the org's real policy:

- **Minor/patch/pin bumps, clean or mechanically repaired to green** → merged with no further ask. "CI should always be green" is exactly `renovate-clear`'s own `readyToMerge` gate — nothing extra to add on top of it.
- **Major/unknown bumps, and anything that needed a real judgement call during repair** → batched and surfaced for a quick go-ahead, same as any other `renovate-clear` run — this skill doesn't lower that bar.

Carry `renovate-clear`'s own Phase 3 report (repaired / merged / awaiting go-ahead / left alone) straight into this skill's combined report — don't re-derive it.

If there are zero open Renovate PRs across both orgs, say so and move on.

---

## Step 4 — Nightly builds (merge existing fixes only — new fixes wait for the call)

```bash
node ~/code/.claude/skills/nightly-health/nightly-health.mjs --org $NIGHTLY_ORG \
  --since "$SINCE_24H" --format markdown
```

Read the bucketed output (`Code Quality`/`DevSecOps Scans`/`Nightly Builds` → real regression; `Black box`/`Integration Tests` → likely flaky; else unclassified) exactly as `nightly-health` describes.

Some of these — particularly `dependency_audit`/CVE-driven `Code Quality` failures — are expected to clear once the Renovate bumps from Step 3 land. **Don't claim they're fixed yet**: nightly-only workflows run on the 06:00 UTC cron, not on push, so a Renovate merge now doesn't re-run last night's failed job — it just means tonight's run should come back clean. Say "expected to clear on tonight's run," not "fixed."

For each **real-regression** failure still standing after Step 3:
1. Look for an **already-open PR** that plausibly fixes it — search recent PRs in that repo (`gh search prs` / `list_pull_requests`), and check project memory for a named in-flight fix (several exist at any time, e.g. a checkout-action regression or a dep-audit logging fix tracked as its own project memory entry).
2. **If a clean, green, mergeable fix PR already exists** → merge it (squash + delete-branch, matching org convention). Landing existing work is not "fixing" in the sense the stop condition below means.
3. **If a candidate PR exists but needs repair** (conflict, red CI, anything requiring a code change to make it mergeable) → **do not repair it in this run.** Repairing crosses into "fixing," which needs Harry's call. Name the PR and what's blocking it in the report instead.
4. **If no PR exists at all** → **do not open one, write a fix, or touch the failing repo.** List the failure plainly in the report under "awaiting your go-ahead to fix."

This is a deliberately different bar from Step 3: Renovate fixes are pre-authorized by the org's own policy; nightly-build fixes are not, until Harry says so for that specific failure.

---

## Step 5 — Report

Write (or append to, if a run already happened today — see Step 1) `~/Documents/obsidian/Digests/Distraction-Duty/<YYYY-MM-DD>.md`:

```markdown
---
tags: [distraction-duty]
date: <YYYY-MM-DD>
---
# Distraction Duty — <Day>, <YYYY-MM-DD>
Ticket: [<FUSE-NNNN> — Sprint N Distraction Duty](<jira-url>)   <!-- or "no active ticket found" -->

## Run @ <HH:MM> UTC

### 🔥 Prod status (last 24h)
**Status** — <one line: "all clear", or the live items>

**Incidents** — <"none", or one per line with link/sev/status>

**Monitors**

| Status | Count |
|--------|-------|
| ✅ OK | <n> |
| ⚠️ Warn | <n> |
| 🔴 Alert | <n> |
| ⬜ No Data | <n> |
| 🔇 Muted | <n> |

**Flapped in the last 24h** — <"nothing beyond the rollup above", or per monitor: name, cycle count, likely driver (tag breakdown), and a link to the memory entry/ticket if this is already tracked>

**Key metrics** (24h)

| Metric | Value |
|--------|-------|
| Records ingested | <n> |
| Platform failures (`create_data_failure`) | <n> |
| Fuse API availability | <n>% |
| Worst Pub/Sub backlog | <n> (<subscription>) |

<the `health-run` block — see "The health-run block" below; this, not the prose table above, is what orient's /health trend plots>

### 📦 Renovate PRs
<renovate-clear's own Phase 3 report, carried through verbatim: repaired / merged (repo#number → sha) / awaiting go-ahead / left alone>

### 🌙 Nightly builds
<nightly-health's one-line rollup>

**Merged existing fixes** — <"none", or repo#PR → sha, one per line>

**Blocked fix PRs found (not repaired this run)** — <"none", or repo#PR + what's blocking it>

**Awaiting your go-ahead to fix** — <"none", or one line per failure: repo, workflow/job, real-regression cause if cheaply known>
```

Print the same content as a terminal summary — this is a status report, not a silent file write.

### The `health-run` block

Every run's `### 🔥 Prod status` sub-section carries this block below its prose tables. The prose is
for reading; **the block is what orient's `/health` page actually plots**, and it exists because the
prose alone couldn't be trusted — across Aug–Sep 2026 the key-metrics table silently alternated
between a 24h and a 3-day window, which plots a 3-day total against a 24h one and invents a spike.
Each row carries its own `window`, and orient drops any point whose window isn't `24h`.

````markdown
```orient-data
{"v":1,"kind":"health-run","columns":["metric","label","value","unit","window","detail"],"rows":[
 {"metric":"monitors_ok","label":"Monitors OK","value":46,"window":"point"},
 {"metric":"monitors_warn","label":"Monitors warn","value":0,"window":"point"},
 {"metric":"monitors_alert","label":"Monitors alert","value":0,"window":"point"},
 {"metric":"monitors_no_data","label":"Monitors no-data","value":12,"window":"point"},
 {"metric":"monitors_muted","label":"Monitors muted","value":0,"window":"point"},
 {"metric":"incidents","label":"Open incidents","value":0,"window":"point"},
 {"metric":"records_ingested","label":"Records ingested","value":29545,"unit":null,"window":"24h","detail":null},
 {"metric":"platform_failures","label":"Platform failures","value":43,"unit":null,"window":"24h","detail":null},
 {"metric":"api_availability","label":"Fuse API availability","value":99.66,"unit":"%","window":"24h","detail":"fleet-wide prod, 23/6788 failed"},
 {"metric":"worst_backlog","label":"Worst Pub/Sub backlog","value":34,"unit":null,"window":"24h","detail":"dedupe create_record_request_sales_order sub"}
]}
```
````

Rules, each of which exists because breaking it produces a confident wrong number rather than a
visible error:
- **`metric` keys are the contract**; `label` is display text and can be reworded freely.
- **`value` is a bare number** — no commas, no `%`, no `(subscription)` suffix. Units go in `unit`,
  qualifiers in `detail`. A string value is dropped.
- **`window` is mandatory and honest**: `24h`, `3d`, or `point` for point-in-time state. Never label
  a 3-day figure `24h` to make it plot — a gap is the correct output.
- **Omit a row you didn't measure; never write 0 for "not checked".** If Datadog is down, leave the
  monitor and incident rows out — orient shows an honest gap, whereas 0 reads as "nothing wrong".
**Validate the blocks after writing**, best-effort:

```bash
node ~/projects/orient/scripts/validate-blocks.mjs <the file you just wrote>
```

Exit 1 lists anything off-contract — a `value` that's a string rather than a bare number, a `window`
outside `24h`/`3d`/`7d`/`point`, a typo'd block kind. Worth fixing immediately: a malformed block
still renders, it just renders **wrong**, and nothing downstream will say so. Missing command (orient
not installed) → skip it; it's a guard, not a gate.

- **Availability is fleet-wide prod** (`sum:fuse.request.failure{environment:prod}` over
  `sum:fuse.request{environment:prod}`), not `{service:api-gateway}` — that scope has no failure
  series at all and reported an unverifiable flat 100%.

---

## Stop conditions

- Never merge a Renovate major/unknown bump without a go-ahead — this skill doesn't loosen `renovate-clear`'s own gate.
- Never repair, open a branch for, or write a fix for a nightly-build failure without Harry's explicit go-ahead for that failure. Merging an already-clean existing fix PR is the one thing allowed unconditionally here.
- This is read-only diagnosis for prod — never apply a production fix, approve or trigger a deploy, or silence/edit a monitor as part of this run. If Step 2 looks like a live incident rather than known noise, hand off to `incident-response`.
- Worktrees only for any repair work done via `renovate-clear` — never edit or `git stash` in a repo's main checkout, per this org's CLAUDE.md.
