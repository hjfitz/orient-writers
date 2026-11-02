---
name: explain
description: Write a terse, bottom-line-up-front explainer for orient — a bug, an investigation, a decision, a migration step, an architecture change — in a military-brief style, with a confidence-rated BLUF, basis-tagged claims backed by numbered evidence, and diagrams orient draws itself. Defaults to explaining the current conversation's work; given an explicit target (a PR, ticket, incident, service, or code path) it researches that instead; with --system <service> it writes present-tense system truth into that service's Waypoint explainers; with --check it measures which cited code has moved since an explainer was verified. Trigger when the user asks to explain what happened, write up/document this, refresh/check an explainer, or "/explain" (optionally followed by a target).
---

# Explain

A short page a human reads cold in under a minute and acts on. It is **not** the Confluence postmortem (`incident-postmortem` owns that) and **not** a digest. It is read in **orient**, not Obsidian, so it is not plain markdown: it opens with a BLUF, tags every claim with its basis, cites numbered evidence, and carries typed blocks (`orient-bluf`, `orient-evidence`, `orient-flow`, `orient-sequence`) that orient draws natively. Everything else is ordinary markdown.

Modes, chosen by the argument:

- **No target** → explain the current conversation's work. Use what is in context; do not re-research what you just did.
- **Explicit target** (a PR, a ticket, an incident, a service, a code path, "why does X do Y") → research it fresh (GitHub, Fuse MCP, Jira, Datadog, the code) before writing.
- **`--system <service>` (optionally `--update <slug>`)** → a **system explainer**: how the system works *now*. Present tense, no ticket numbers or dates in the body. Lands in the service's Waypoint folder. Invoked by `waypoint-work` at sign-off, by orient's refresh button, or directly.
- **`--check [<service> | --all]`** → no writing. Run the drift check (Step 6) and report which anchors moved.

If there is no substance and no target, ask what to explain.

## Configuration

```
VAULT   = ~/Documents/obsidian
DIR     = ~/Documents/obsidian/Explainers                        # event modes
SYSDIR  = ~/Documents/obsidian/Engineering/<service>/explainers  # --system mode
LINT    = node ~/.claude/skills/explain/lint-explainer.mjs <file> [--mode system|event|overview|architecture|blocks]
          # overview/architecture: the two Waypoint docs that share this language (see waypoint-onboard/doc-shapes.md); blocks: validate typed blocks only
DRIFT   = python3 ~/.claude/skills/explain/explain-drift.py <file>... [--write] | --all
```

## Step 1 — Fix the BLUF before anything else

State, in one or two sentences, **the conclusion** ("X broke because Y", "we chose A over B because C", "the flow for Z is this"), then how sure you are, then **what the reader must do**.

- `bluf` — the conclusion. Active voice. No story, no "this document".
- `confidence` — `high` (read it in code, logs or a source of record), `moderate` (inferred from consistent evidence), `low` (a hypothesis).
- `action` — what the reader must do, or `none`. `none` is a decision, not an omission.

If you cannot write the BLUF, you are not ready to write: go and find the missing piece. Do not invent timestamps, numbers or mechanisms. An honest `UNKNOWN` beats a plausible filler, because an explainer is often read instead of the source.

## Step 2 — Write it in the house style

- **Bottom line first.** Every section leads with its conclusion, then the reason.
- **One idea per sentence. 22 words or fewer. Active voice.** Name the actor: "The handler drops the record", not "the record is dropped".
- **Short words, no hedges.** Delete *probably, might, basically, essentially, quite, very, just, simply, clearly*. State it, or tag it `ASSESSED` or `UNKNOWN`.
- **Numbers carry units, dates are ISO, times are UTC.**
- **Lists over paragraphs** for parallel facts. Seven items or fewer.
- **Every claim leads with its basis and cites its evidence** (below). A claim with no basis is a guess.
- **Cut.** If the honest answer is three bullets, write three bullets. Event explainers stay under about 600 words, system explainers under about 1,300; the lint warns past that.

### Basis tags

Start each claim (a paragraph, or a top-level bullet) with one bold word:

- `**CONFIRMED**` — you read it in code, logs, a ticket or a source of record, this session.
- `**ASSESSED**` — you infer it. Say what from.
- `**UNKNOWN**` — you could not establish it. Say what is missing.

orient draws the word as a tag, so it survives a screenshot. Do not tag headings, table rows or the BLUF.

## Step 3 — Write the page

Event modes (`DIR/<YYYY-MM-DD>-<slug>.md`):

````markdown
---
tags: [explain]
date: <YYYY-MM-DD>
thesis: "<the BLUF text, quoted>"
confidence: <high|moderate|low, the same as the BLUF block>
---
# <One-line headline, not a generic title>

```orient-bluf
{ "v": 1, "bluf": "<conclusion>", "confidence": "high", "action": "none" }
```

## Situation
- **CONFIRMED** <what is true, and why this came up> [1]

## Assessment
- **CONFIRMED** <the mechanism or root cause, with the evidence> [2]
- **ASSESSED** <an inference, and what it rests on>

## Open items
| Item | Owner | By |
|---|---|---|
| <what is still owed> | <who> | <YYYY-MM-DD> |

## Evidence
```orient-evidence
{ "v": 1, "items": [ { "id": 1, "kind": "pr", "ref": "owner/repo#12" } ] }
```
````

System mode (`SYSDIR/<kebab-mechanism-name>.md`, no date prefix, stable slug) uses the same BLUF block, then `## Mechanism`, `## Boundaries`, `## Constraints`, `## Evidence`, `## Related` (`[[wikilinks]]` to sibling explainers and the service's architecture doc). Its frontmatter adds the staleness anchor:

```yaml
tags: [waypoint, explainer, <service>]
thesis: "<the BLUF text, quoted>"
confidence: <high|moderate|low, the same as the BLUF block>
updated: <YYYY-MM-DD>
verified: <YYYY-MM-DD>
verified_sha: <service repo short HEAD of origin's default branch, after a fetch>
verified_paths:
  - <each source path the claims rest on, repo-relative>
```

`thesis:` **must equal** the BLUF text (`wp` and the Explainers view read it). Quote it, since it will contain a colon. `confidence:` **must equal** the BLUF block's confidence; the Explainers table shows and sorts on it. System explainers describe **mechanism, not history**: delete superseded reasoning, do not annotate it.

**Update before you create.** `python3 ~/.claude/waypoint/wp.py context <service>` lists existing explainers with their theses. If one covers this ground, edit it in place (`--update <slug>`) and re-stamp `verified`, `verified_sha`, `verified_paths` and `updated`: a re-verification is what an update is. An explicit `verified_paths: []` claims the page never goes stale; rare, and prefer real paths.

## Step 4 — The typed blocks

Each is JSON in a fenced block, parsed as data. A bad block shows as a visible error on the page, so run the lint.

**`orient-bluf`** — exactly one, before the first `##`. Fields: `bluf`, `confidence` (`high|moderate|low`), `action`.

**`orient-evidence`** — one, at the end. `items[]` of `{ id, kind, ref, note? }`, ids positive and unique. Prose cites a row as `[3]`; orient links it. Kinds and refs:

| kind | ref |
|---|---|
| `code` | `path@sha` or `path@sha:L10-30` — the repo-relative path and the commit you read it at. **This is what the drift check measures.** |
| `pr` | `owner/repo#n` |
| `ticket` | `FUSE-123` |
| `log` | the query, or the line, verbatim |
| `doc` | a vault path or title |
| `url` | a full URL |

Cite what you actually read, at the sha you read it. Use line ranges only when you read those lines.

**`orient-flow`** — a diagram, when a structure or path is hard to hold in prose. At most 12 nodes in practice; one per page is normal. Fields: `title?`, `nodes[]` of `{ id, label, sub?, kind?, service?, tone?, ev? }`, `edges[]` of `{ from, to, label?, style? }`.
- `kind`: `service | topic | store | step | external` (default `step`). Say something only when the kind matters.
- `service`: a repo name. Draws its identity colour and links to its Waypoint docs.
- `tone`: `alert` marks the failure point, `accent` the point of the page.
- `ev`: evidence ids that back the node.
- A cycle is fine; its closing edge is drawn round the side.
- Keep labels short (a few words) and put detail in the prose. Do not add a node a reader does not need.

**`orient-sequence`** — for an order of calls between parties. `actors[]` (2 to 8) of `{ id, label, service? }`, `steps[]` of `{ from, to, label, kind?, note?, tone?, ev? }` with `kind` `call|return|async`. Steps are numbered on the page; cite "step 3" in prose.

Do **not** write mermaid. Pick `orient-flow` for structure and branching, `orient-sequence` for ordered calls, a table for a chronology of more than five events, and a bullet list for fewer.

## Step 5 — Lint, then save

Run `LINT` on the file. **Errors are blocking**: a bad block, a missing or late BLUF, a `thesis:` or `confidence:` that differs from the BLUF, a `[n]` with no evidence row, a code anchor that is not `path@sha`, a system explainer without its anchor. **Fix every warning** you can: long sentences, hedges, passive voice, an untagged claim, a missing section, a page over its cap. Leave one only when you can say why it is right.

Save event pages to `DIR/<YYYY-MM-DD>-<slug>.md`. If a file for the same slug exists today, append a `## Update @ HH:MM` section rather than a near-duplicate. A system explainer is always edited in place.

Then, for a system explainer, run `DRIFT <file> --write`. It stamps `commits_behind`, `drifted_evidence` and `drift_checked` into the frontmatter, so orient shows how many anchors have moved. Print the thesis and the file path back as the response. No Slack post and no PR comment unless asked.

## Step 6 — `--check`: measure drift

`DRIFT --all` (or the files of one service) asks git, for every `code` anchor, whether that path has changed on the default branch since the anchor's sha, and whether the doc's `verified_paths` have moved since `verified_sha`. A path that vanished, or a sha the repo cannot reach, counts as moved.

Report the result as a table: explainer, anchors moved of total, commits behind. For each moved anchor, **read the code at the new head**. Then either:

- the claim still holds → re-cite it at the new sha and keep its tag, or
- the claim changed → correct the page to present-tense truth, delete what is superseded, and re-stamp.

Re-run the lint and `DRIFT --write` afterwards. Never clear `drifted_evidence` by hand.

## Stop conditions

- No target and no substance in the conversation → ask what to explain.
- A claim cannot be grounded in something real → tag it `UNKNOWN` or leave it out. Never fabricate to fill a section.
- The subject is a live, unresolved production incident → say so and point at `incident-response`.
- A system explainer's code claims cannot be verified because the repo is unreachable → stop; do not stamp an anchor you did not check.
