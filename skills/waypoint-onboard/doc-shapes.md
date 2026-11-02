# Waypoint doc shapes: overview and architecture

`overview.md` and `architecture.md` are read in **orient**, so they share the explainer design language:
a BLUF at the top, typed blocks orient draws itself, and numbered evidence at the end. Prose stays
ordinary markdown.

Lint before you finish: `node ~/.claude/skills/explain/lint-explainer.mjs <doc>` picks the mode from the
file name. Errors block; fix every warning you can.

## What differs from an explainer

- **The doc is anchored to a commit** (`verified_sha`, `verified_paths`), so an unmarked claim reads as
  *confirmed at that anchor*. Do not tag every paragraph. Tag only `**ASSESSED**` and `**UNKNOWN**`
  claims, so the doubtful ones stand out.
- **Present tense, mechanism not history.** Same rule as a system explainer: delete superseded reasoning.
- `thesis:` and `confidence:` in the frontmatter **must equal** the BLUF block, as for an explainer.
- A diagram is `orient-flow`. **Never mermaid, never an ASCII box drawing.** A directory tree is a plain
  code block, since it is a listing and not a diagram.

## overview.md (under about 700 words)

````markdown
---
tags: [waypoint, <service>]
title: <service> — overview
thesis: "<the BLUF text, quoted>"
confidence: high
verified: <date>
verified_sha: <short sha>
verified_paths: [<paths the claims rest on>]
---
# <service> — overview

```orient-bluf
{ "v": 1, "bluf": "<what it is, the one thing it owns, why it is separate>", "confidence": "high", "action": "none" }
```

## Responsibility
<What it owns, in two to four sentences or bullets.>

## Why it exists separately
<The boundary, and why it is deliberate.>

## Neighbours
```orient-flow
{ "v": 1, "title": "<service> in context", "nodes": [ ... ], "edges": [ ... ] }
```
<One or two lines on the arrows that matter. Upstream, this service, downstream, its stores. Ten nodes at most.>

## Where the reference lives
<Where the deep reference is, and what not to trust. Link `[[architecture]]` and `[[known-context]]`.>

## What deliberately isn't here
- **<Thing>.** <Who owns it instead.>

## Evidence
```orient-evidence
{ "v": 1, "items": [ { "id": 1, "kind": "code", "ref": "<path>@<sha>" } ] }
```
````

`confidence` is `high` only when you read the claims in the code at `verified_sha`. Otherwise `moderate`,
and say what is unverified under the relevant section as `**UNKNOWN**`.

## architecture.md (under about 2,600 words)

Same frontmatter and BLUF. The BLUF states the service's shape in one or two sentences, and its `action`
names the guardrail a newcomer is most likely to trip over (or `none`).

1. `## Guardrails`, unchanged: at most six, typed and path-tagged (`[kind:Gn] … — paths: …`) so
   `wp context --paths` can still push them.
2. A structure diagram as `orient-flow` under the first structural section. Several small flows beat one
   large one: split inbound from outbound rather than drawing a cycle.
3. The existing structural sections (interfaces in and out, persistence, runtime). Keep tables for
   reference rows.
4. `## Evidence` last, as `orient-evidence`, with `[n]` citations in the prose where a claim is
   non-obvious.

## Edge cases

- A service with a single page of truth writes `overview.md` only; the lint's architecture mode does not
  apply.
- A service whose structure is a flat list of packages (a monorepo of libraries) draws the **dependency
  graph** as its flow.
