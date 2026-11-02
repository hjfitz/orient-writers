---
name: week-roundup
description: Draft the end-of-week "Fuse this week" team roundup for Slack. Gathers the week's merged PRs, Jira epic progress + product changelog, incidents + reliability metrics (Datadog, prod & dev), engineering/platform changes, cross-team support, and business/adoption signals, then composes a concise factual Slack post (🚀 Product progress / ⚙️ Engineering / 📈 Reliability & operations / 💡 Highlights / 🤝 Cross-team & business / 🔭 Up next) for Harry to approve, auto-archives it to Obsidian, and leaves posting to Slack entirely to Harry. Use on Friday afternoons, or when the user asks for the end-of-week roundup, Friday roundup, week wrap-up, or team weekly post.
---

# Week Roundup (team-facing)

The **Friday team post** — the third altitude next to `/morning-digest` (daily ops, private) and `/weekly-digest` (personal retro, private). Written for the team and read by non-engineers too.

The post independently answers one question — **"What should Engineering communicate this week?"** — from its own evidence. It is not composed around, or in reaction to, anyone else's message; it stays complementary to Product by virtue of its structure and evidence. Product milestones are included where they give useful context.

Two registers, deliberately separated:
- **The body is factual** — every line traces to a changelog row, epic, PR, ticket, metric, or incident record gathered below. No vibes-only claims, and no generic "awesome work" filler inside the generated body.
- **The warmth is Harry's** — the draft leaves `_(your line)_` slots for the personal intro and sign-off rather than faking his voice.

**Claude never posts to Slack — ever.** Compose → show the draft → Harry edits/approves → auto-archive to Obsidian → Harry copies it and posts it himself, in his own time.

---

## Configuration

```
WEEK_START     = Monday of the current week
GITHUB_ORG     = gfs-bifrost                    # identity via get_me; exclude bot authors
JIRA_PROJECT   = FUSE
SLACK_CHANNEL  = #bifrost-forge (C09PBES3MHT)   # override per-run if Harry names another channel
SLACK_INCIDENTS= #incidents (C09AP9ZTN7R)
INCIDENT_IO    = https://api.incident.io/v2 — key INCIDENT_IO_API_KEY in ~/.secrets
DATADOG_SCOPE  = domain:fuse — compare env prod AND dev, this week vs last week
TEAM           = Matt Shaw, Schuster Efigenio, Harry Humby, Kyle Chandler, Nylah Klasson (+ Harry)
ARCHIVE_FILE   = ~/Documents/obsidian/Digests/Roundups/<YYYY-Www>.md
MAX_BULLETS    = 12–18 across all sections       # it's a Slack message, not a report
```

## Step 1 — Setup

```bash
mkdir -p ~/Documents/obsidian/Digests/Roundups
TODAY=$(date +%F)
ISO_WEEK=$(date +%G-W%V)
WEEK_START=$(date -d 'last monday' +%F)          # run on Friday; if run ON Monday use today
PREV_WEEK_START=$(date -d "$WEEK_START -7 days" +%F)
```
Resolve GitHub identity via `mcp__github__get_me`. If this week's `/weekly-digest` or the week's daily notes exist in the vault, skim them first — they pre-surface themes the queries below will confirm.

## Step 2 — Gather in parallel

Fan out **five subagents in one message**. Each returns a compact markdown block — triaged, deduped, every item carrying a source link (kept for the receipts thread and archive, not the main post).

**A. GitHub — what merged**
- `is:pr is:merged org:gfs-bifrost merged:>=WEEK_START sort:updated-desc`, excluding bot authors (`renovate`, `dependabot`, `*[bot]`).
- Group by **author**, then by theme (same ticket/epic → one item). For each: repo#num + URL, author login, ticket key if any, one plain-English line on what it does *for the platform* (not the diff).
- Flag milestone-shaped items (feature complete, cutover, major version, shared-package publish) and engineering-shaped items (infra migrations, CI/workflow, DX, observability) — these feed the ⚙️/📈 classification in Step 3, and epic-status changes feed 🚀 via gather B.

**B. Jira + Confluence — epics first**
The unit of product reporting is the **epic**, not the ticket.
- Done this week: `project = FUSE AND status CHANGED TO Done DURING ("<WEEK_START>", now())` — capture assignee and epic link.
- Progressed: `project = FUSE AND status CHANGED DURING ("<WEEK_START>", now()) AND statusCategory != Done` — flag anything that moved **into QA/UAT/Review**.
- **Epic view (the product story):** for each epic the above work touched, summarise its state change in capability language — did the epic move into QA/UAT, reach feature-complete, get released? Note which individual tickets *materially changed the epic's status* (those may be cited; the rest are receipts).
- **Classify each epic/ticket**: product development vs **onboarding/adoption** (customer migrations, config-only setup) vs operational. Onboarding is not product development — report it as business/adoption activity unless it drove a genuine product capability or product decision.
- Product changelog: via `mcp__fuse__lookup-changelog-page`, list rows added this week — the **authoritative** "product capability delivered" source (priority 1 for 🚀).
- Next: active epics, epics entering refinement, and confirmed sprint/roadmap priorities → the top 2–3 **plain-English, verb-led product themes** (no onboardings, no ticket keys, no inferred timelines or capacity).

**C. Datadog — reliability, with real numbers**
- Skill discovery first (`list_datadog_skills`), then compute for **prod and dev separately**, this week vs the like-for-like span of the prior week:
  - **Availability**: `fuse.request.failure` / `fuse.request` per instrumented service → a % per env, with the instrumented scope stated. Name standout services only where more than one emits the metric.
  - **Throughput**: records ingested (`sum:fuse.dedupe.event.handled`) — week total, direction vs prior.
  - **Failures**: `create_data_failure` publish count — week total, direction.
- Monitors: any that went to Alert during the week — count + the notable ones. Known false-firers (ingress-stalled `302536181`, low-volume No-Data) marked benign.
- Datadog incidents opened/closed in the window.

**D. Incidents — incident.io + #incidents**
- `GET $INCIDENT_IO/incidents` (Bearer key from `~/.secrets`), filter to created **or** closed in the window: severity, duration, status, one-line summary each. Note carried-in incidents still open.
- Read `SLACK_INCIDENTS` since `WEEK_START` for informal declarations or investigation threads that concluded.
- A **quiet week is a result**: "no new incidents" is a 📈 line, not an empty section.

**E. Slack — decisions, cross-team support, business signal**
- `SLACK_CHANNEL` since `WEEK_START`: threads where a real **engineering decision** landed (convention adopted, approach chosen, migration agreed) — decisions, not chatter.
- **Cross-team support**: team members helping outside the team — support asks answered, other teams unblocked, onboarding help. Search team members' names/mentions in non-team channels, best-effort.
- **Business signal**: praise/feedback from the business side, customer go-lives, UAT feedback, stakeholder reactions.

## Step 3 — Compose the draft

Classify every candidate item into **exactly one** section below — the same fact never appears twice in the post. Drop empty sections without comment.

**Section rubric:**

- **🚀 Product progress** — product capability moving forward, described at **epic or product-feature level**. Source priority: (1) product changelog entries, (2) epic status/progress, (3) release/UAT milestones, (4) an individual ticket only when it materially changes an epic's status. Wording like "Returns is ready to enter QA", "Pick/Pack confirmations entered UAT", "the Template Library reached feature-complete". **Milestone verbs are precise**: `Ready for QA` → "ready to enter QA"; QA accepted / testing begun → "entered QA"; QA complete → "cleared QA"; UAT begun → "entered UAT". Never upgrade a `Ready for…` status into "moved into / entered" without evidence testing actually began. **Team workflow fact**: a ticket at `Ready for QA` or later implies its code is **merged** — describing that work as code-complete/landed is safe even when the merge wasn't separately evidenced. That licenses build-completion claims, not QA-progress claims; the verbs above still gate those. The section explains **what capability moved forward** — never enumerate the underlying tickets/PRs, never present implementation details as product headlines.
- **⚙️ Engineering** — changes to **how Fuse is built, operated, secured, or evolved**: platform/infrastructure migrations, architecture decisions, developer experience, preview environments, security-workflow standardisation, observability improvements, shared packages/reusable workflows, tech-debt reduction. Describe the change **and its durable effect**: "All services now use the new cross-entity topics, allowing the six legacy topics to be retired."
- **📈 Reliability & operations** — availability and failure metrics, incidents, **production defect resolution**, CVE remediation, operational investigations, support issues, security scanning results. Don't mix these into product progress unless the work directly enabled a product milestone. Every metric computed from **this week's** data and **accurately scoped** (name the instrumented surface; never claim more nines than the data shows). State a percentage only when the calculation positively establishes **both** request and failure counts for the stated scope — an empty/missing failure series reads as "no failures recorded", never as a computed 100%.
- **💡 Highlights** — **outcome-led recognition**: a named contribution connected to its impact ("Matt added reason-tagged metrics, making dropped confirmations immediately visible"; "Schuster made confirmation-file writes atomic, removing a race condition that could silently lose orders"). No generic praise; no lines that only restate the implementation. **Do not force equal representation** — include people only where there is a concrete, notable contribution; omission is silent and fine.
- **🤝 Cross-team & business** — support given across teams, stakeholder/business feedback, and **customer onboarding/adoption activity**. Onboarding is adoption, not product development: it belongs here (or is omitted when routine operational work); it surfaces in 🚀 only when it requires a genuine product capability, feature, or product decision — and then the *capability*, under its epic, is the headline.
- **🔭 Up next** — 2–3 plain-English **product themes** derived from active epics, epics entering refinement, confirmed sprint/roadmap priorities, and product changelog plans. Verb-led: "Move Returns through QA", "Refine Work Orders", "Begin Smart Confirmation Routing". Every theme must be framed at **epic/capability level with Jira or changelog support** — a queue of finishing tasks ("finish X settings, Y ordering") doesn't qualify: resolve it to the capability it advances, move the detail to ⚙️, or omit it. **Never** delivery-timeline promises ("will ship next week") unless explicitly confirmed; never inferred capacity; never routine customer onboardings.

**Editorial rules:**
- **12–18 bullets total.** One epic-level statement beats several ticket-level ones. Don't inflate routine work into a headline.
- **Plain English, no identifiers**: no Jira keys, no repo#num, no jargon in the body — non-engineers read this. Evidence and source links live in the receipts thread and the archive.
- **Timing is explicit**: a mid-week run says "so far this week" on every point-in-time metric and status, and nothing implies the week is complete. The Friday run **refreshes every metric and status** — never reuse mid-week values.
- **Emoji**: the section emojis, plus at most one or two workspace-culture ones (verify customs exist via `slack_search_emojis` before using).

```
*Fuse this week* — w/c <WEEK_START, e.g. 20 July>

_(your intro — one warm line; the generated body stays factual)_

*🚀 Product progress*
• <capability that moved forward, epic-level — "Returns moved into QA …">

*⚙️ Engineering*
• <change + durable effect — "… allowing the six legacy topics to be retired">

*📈 Reliability & operations*
• <incidents/availability line, honestly scoped> / <prod defect resolved> / <CVE waves cleared>

*💡 Highlights*
• <First name> <contribution → impact, one line>

*🤝 Cross-team & business*
• <support given, feedback heard, onboarding/adoption activity>

*🔭 Up next*
• <verb-led product theme — "Move Returns through QA">

*📊 At a glance*
• <N> PRs merged
• <N> Jira items done, <N> progressed
• <N> new incidents
• <N> API requests (instrumented gateway), <failures — "no failures recorded" if the series was empty>
• <N> records processed (<↑/↓ vs prior week>)
• <CVE line — e.g. "2 CVE waves cleared (17 PRs)">

_(your sign-off)_
```

**At a glance** closes the post: 4–6 terse counts, sitting **outside** the 12–18 bullet budget. Every figure must be positively established from this week's gathered data (a count the gather actually returned — never an estimate), scoped honestly in as few words as possible (same evidence-safe rules as 📈), and suffixed "so far" framing on a mid-week run. Default set: PRs merged (bots excluded) · Jira done + progressed · new incidents · API requests through the instrumented gateway · records processed (with direction vs prior week) · CVE remediation. Adapt the set to the week — drop a figure that wasn't gathered rather than approximating it.

## Step 4 — Approve, then archive automatically (Harry posts it himself)

1. **Show the full draft in the terminal** and iterate until Harry approves. He may rewrite the intro/sign-off slots or hand back edits — apply them verbatim. Print it in a fenced code block written in **Slack-native formatting**, since he pastes it straight into the Slack composer: `*bold*` (single asterisks — pasted `**markdown**` shows literal asterisks), `•` or plain lines for bullets, `:emoji:` codes (composer converts them on send), bare URLs only if a link is essential.
2. **Archive automatically once approved — no need to ask.** Save to `ARCHIVE_FILE` (frontmatter `tags: [roundup]`, `week: <ISO_WEEK>`): the final approved text (intro/sign-off filled in, or omitted if he skipped them) plus a **receipts** section listing the evidence links behind each claim — merged PRs, tickets, epics, Datadog dashboards, incident records. This is the only record kept; there's no posted-message permalink to add since Claude doesn't post it.
3. **Never touch Slack.** Don't call `slack_send_message`, don't create a `slack_send_message_draft`, don't offer to post it. Posting — and when, and to which channel — is entirely Harry's call; he copies the approved text out of the terminal or the archive file himself.

Then print a one-line terminal summary: e.g. `W29 roundup · 2 epics advanced · 14 PRs · prod 99.98% · 0 incidents · approved → archived`.

---

## Notes & caveats

- **Claude never posts to Slack, in any form** — no `slack_send_message`, no `slack_send_message_draft`. The archive step happens automatically once Harry approves; posting to the channel is entirely his, on his own timing.
- **Numbers are computed, not remembered.** A reliability claim without this week's query behind it doesn't go in the post — and its scope (which services, which env, partial week) is stated, not implied.
- **Product progress speaks in capabilities, not tickets.** If a bullet can't be phrased as "what can the product/user do now (or soon) that it couldn't", it belongs in ⚙️/📈, not 🚀.
- **Onboarding ≠ product development.** Customer migrations and config-only setup are adoption activity (🤝) or omitted when routine — never 🚀 or 🔭 headlines unless a genuine product capability/decision came out of them.
- **Recognition is outcome-led and unforced** — a named contribution tied to its concrete impact. No generic praise, no quota; someone with nothing notable this week is silently absent.
- **One fact, one section.** If something is a person's highlight, it isn't also a reliability bullet — pick the section where it communicates most.
- **A quiet week is fine.** "No new incidents, reliability held, heads-down on X" is a legitimate — and reassuring — roundup.
- **Run manually on Friday afternoons.** No scheduler; it's interactive by design (the draft-approve loop is the point).
