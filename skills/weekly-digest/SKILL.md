---
name: weekly-digest
description: Build the EM weekly review — a reflective, Modern Wisdom–style self-review plus a look-ahead at next week, grounded in the week's daily digest notes. Reads the week's `Digests/<date>.md` notes (done vs carried todos, recurring themes), adds a few fresh week-level queries (PRs merged, tickets closed, next week's calendar), and writes a weekly note to the Obsidian vault. Use on Fridays, or when the user asks for their weekly digest, week in review, weekly review, or Friday review.
---

# Weekly Digest (EM self-review)

A **Friday** companion to `/morning-digest`. Different altitude: not "what's on fire today" but a **reflective self-review** of the week + a **look-ahead** to next week. Manual, like the daily.

Two things only (the user chose these): a **Modern Wisdom–style self-review** and a **look-ahead**. No team-throughput dashboard, no prod/ops rollup.

It's **hybrid**: synthesize the week's daily notes for the lived detail, then add a few fresh week-level queries to ground the retro in what actually shipped. The reflective parts are **seeded from evidence but meant for Harry to finish** — draft the observable answer, leave the felt parts (energy, gratitude) as prompts.

---

## Configuration

```
VAULT        = ~/Documents/obsidian
DAILY_DIR    = ~/Documents/obsidian/Digests/<YYYY-MM>      # dailies are grouped in month subfolders
WEEKLY_FILE  = ~/Documents/obsidian/Digests/Weekly/<YYYY-Www>.md
GITHUB_ORG   = gfs-bifrost      # identity via get_me
JIRA_PROJECT = FUSE
```
Same conventions as the daily skill: **tables** for scannable bits, `[[wikilinks]]` for people/customers/Jira keys, a **blank line between any `**bold heading**` and the table beneath it**, links on items, and a sources-status footer.

---

## Step 1 — Setup

```bash
mkdir -p ~/Documents/obsidian/Digests/Weekly
TODAY=$(date +%F)
ISO_WEEK=$(date +%G-W%V)                 # e.g. 2026-W25
WEEK_START=$(date -d 'last monday' +%F)  # Monday of this week (run on a weekday); fall back to 7 days ago if odd
echo "$ISO_WEEK  $WEEK_START → $TODAY"
ls -1 ~/Documents/obsidian/Digests/[0-9][0-9][0-9][0-9]-[0-9][0-9]/*.md 2>/dev/null   # daily notes in YYYY-MM month folders (excludes Digests/Weekly/); use those dated >= WEEK_START. A week spanning a month boundary pulls from two folders.
```
Resolve GitHub identity via `mcp__github__get_me`. If no daily notes exist for the week, say so and lean on the fresh queries.

## Step 2 — Read the week's daily notes (synthesis source)

Read each `Digests/<YYYY-MM>/<date>.md` from `WEEK_START`..`TODAY` (dailies live in month subfolders; a week crossing a month boundary spans two of them). Pull out:
- **Todos done vs still open** — checked (`- [x]`) vs unchecked (`- [ ]`) across the week; note the `(carried ×N, since <date>)` markers — high-N items are the chronic ones.
- **Recurring themes** — anything that appeared in *Needs me today* on multiple days (a standing blocker, a thread that wouldn't die).
- **Meetings / 1:1s had**, and any prod notes worth remembering.

## Step 3 — Fresh week-level queries (the hybrid bit)

- **Shipped (GitHub):** `is:pr is:merged author:<login> org:gfs-bifrost merged:>=<WEEK_START>` — what you actually landed.
- **Closed (Jira):** `project = FUSE AND assignee = currentUser() AND status CHANGED TO Done DURING (<WEEK_START>, now())`.
- **Next week (calendar, M365):** notable events + deadlines in the next 7 days (board reviews, releases, the GCP/maintenance-type dates surfaced in dailies). Interactive run, so M365 is available.

## Step 4 — Write the weekly note

Write `WEEKLY_FILE`. Template:

```markdown
---
tags: [weekly-review]
week: <YYYY-Www>
---
# Weekly Review — <YYYY-Www> (<WEEK_START> → <TODAY>)

## 📦 The week in brief
- **Shipped:** <N PRs merged>, <M tickets closed>
- **Todos:** <X done> · <Y still open> (<Z chronic — carried ≥3>)

| Shipped | What |
|---------|------|
| [<repo#num>](<url>) | <title> |
| [[<FUSE-xxx>]] [↗](<browse>) | <summary> — closed |

## 🪞 Self-review

**Wins — what went well**
- <evidence-seeded: what you shipped / unblocked / progressed>

**Friction — what slipped & why**
- <recurring carries (with age), standing blockers, what drained the week>

**Energy audit — more of / less of**
- More of: _(your note — what energised you)_
- Less of: _(your note — what drained you; hint: meeting load was <n> meetings / <h>h)_

**Lessons — what I learned**
- _(your note, seeded with anything observable)_

**The one thing** that would've made the week easier or unnecessary
- _(your note)_

## 🎯 Next week
**Top 3 needle-movers**
1. <from open carry-over + look-ahead>
2.
3.

**Carrying into next week** (open todos, oldest first)

| Item | Age |
|------|-----|
| <todo, with [[wikilinks]]> | carried ×N, since <date> |

**On the calendar / deadlines**

| When | What |
|------|------|
| <date> | [<event>](<webLink>) / <deadline> |

---
_Sources: ✅ daily notes · ✅ github · ✅ jira · ✅ calendar — flip any that **errored or were unavailable** to ⚠️_
```

Then print a one-line terminal summary: e.g. `Week 2026-W25 · 4 shipped · 6 carrying · review written`.

---

## Notes & caveats
- **Reflective sections are seeded, not finished.** Draft the observable answer; leave `_(your note)_` prompts for the felt parts (energy, gratitude, lessons) — this is Harry's review, not Claude's.
- **Run manually on Fridays.** No scheduler (same reasoning as the daily). Interactive, so the M365 calendar is available for the look-ahead.
- Weekly notes live in `Digests/Weekly/` — under the already-bookmarked `📅 Digests` folder.
- If a daily note is missing for a day, note the gap; don't invent the day's activity.
