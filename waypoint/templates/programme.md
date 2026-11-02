---
title: {{title}}
programme: {{slug}}
status: planning
owner: {{owner}}
services: {{services}}
created: {{date}}
updated: {{date}}
tags: [bifrost, migration-state]
---
# {{title}}

<!-- The single source of truth for PROGRESS. The Overview carries the narrative and the verdict;
     this doc is the live ledger a session reads to know what is done and what is next.
     `wp programme status/next/tick` read and write the `## Unit status` tables below, so keep the
     table shape intact. Guidance lives in HTML comments (Obsidian hides them); <angle spans> mark
     what a human or agent must fill in. -->

## Unit status
<!-- The legend line is load-bearing: `wp programme` maps the glyph in the `St` column to a state.
     One table per group / deliverable / tranche — the grouping axis is yours, just a `###` heading.
     REQUIRED columns: `Unit`, `St`. RECOMMENDED: `Summary` (a few words on what the unit is —
     at-a-glance context beside the code; orient shows it, and falls back to the Notes lead when
     absent), `Deps` (comma-separated unit ids that must be ✅ — what `wp programme next` reads to
     find the next unblocked unit), `Risk`, `Tier` (`<model>/<effort>` implementation estimate, set
     with `wp programme set-model`; seeds the plan on promotion), `PR`, `Notes`. Any extra columns
     are preserved untouched. A unit id in bold reads well but isn't required. -->
Legend: ⬜ not started · 🟨 in progress · ✅ merged · ⛔ blocked · ⏸ deferred · ❌ dropped · 🔄 rescoped

### <Deliverable / Group A>
| Unit | St | Summary | Deps | Risk | Tier | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **<U0>** | ⬜ | <a few words: what it is> | | <none> | <sonnet/medium> | | <what this unit does, and how it's verified> |
| **<U1>** | ⬜ | <a few words: what it is> | U0 | <low> | <sonnet/low> | | <depends on U0 being merged> |

## Gates
<!-- A precondition that is NOT a unit — another programme reaching prod, a monitor reading real
     volume, a sign-off. Check the box when it clears; say what it blocks. Not code, so it can't be
     inferred from a diff — this is the structural version of "do not action yet". -->
<!-- Write each as `- [ ] **G1 — <title>** — blocks <unit ids>. <what clears it>` — orient's programme page
     draws a table from the id, the title, the box, and the unit ids after "blocks", and links the
     units it holds up. A gate that waits on another programme names it exactly as its folder is
     named, with the unit ids, in the title (`**G2 — Other Programme U3 + U4 merged**`): orient then
     shows what those units are, where they stand, and how many units they need in all. -->
- [ ] **G1 — <title>** — blocks <unit ids>. <the precondition that clears it>

## Risks
<!-- ★ marks the load-bearing ones. Each: the risk, the mitigation, and its current status. -->
<!-- Write each as `- **R1 ★ <title>** — <mitigation and detail> — <open | standing | closed>.` The
     trailing word is the status pill orient shows; "open" reads as a live risk. -->
- **R1 ★ <title>** — <mitigation and detail> — <status>.

## Decision log
<!-- Dated, newest first. Written as decisions are taken; a decision worth defending in six months
     is a durable record instead (`wp decide --record`). -->
- **<YYYY-MM-DD>** — <the decision, and why>

## Scar tissue
<!-- Do not change, and why. A constraint someone has already been burned by — a deliberate,
     permanent divergence from the reference approach. -->
- <constraint> — <why it is load-bearing>
