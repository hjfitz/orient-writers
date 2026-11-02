---
name: waypoint-onboard
description: Build durable engineering context for one service or application in the Obsidian vault — inspect the repo first, form a provisional model, then interview the user only about what source cannot answer, and write a small set of high-signal docs plus a tiny machine-readable index. Trigger when the user asks to onboard a service into Waypoint, set up Waypoint for a repo, or when waypoint-plan/waypoint-work finds a service that has no vault folder.
---

# Waypoint — onboard

One service, once. Everything lands in `~/Documents/obsidian/Engineering/<repo-name>/`.
**Never write Waypoint artifacts into a code repository.**

`WP = python3 ~/.claude/waypoint/wp.py`

## Step 0 — Locate

`WP locate [service|path]`. If it reports `onboarded: true`, do **not** rewrite: run
`WP stale <service>`, report what drifted, and offer a refresh of only those docs.

## Step 1 — Inspect (read-only, sampled)

Cheap, high-yield reads only. Do not walk the tree.

- `README`, `CLAUDE.md`/`AGENTS.md`, dependency manifests, `mise.toml`/tool pins
- entrypoint + route/subscription registration; `git ls-files | head -200` for shape
- IaC (`iac/`, terraform), CI workflows, test config and one representative test
- `git log --format=%s | head -80` — what kind of work actually happens here
- Fuse MCP `lookup-service` / `lookup-endpoints` / `fuse://` resources if it's a Fuse service

Sample files; read whole files only when small and load-bearing.

## Step 2 — Provisional model (in chat, not a file)

Post a compact bulleted model with confidence per line — `high` (read it),
`med` (inferred), `low` (guess). This is the artifact that generates the interview.
Keep it under ~25 lines.

## Step 3 — Interview the gaps

Generate the questions **from your own `low`/`med` lines**. Rules:

- Never ask what the repo answers. If you can grep it, grep it.
- State your best guess inside each question so the user confirms or corrects rather than composes.
- `AskUserQuestion`, batches of ≤4, **max two rounds**. Stop when the remaining gaps are
  genuinely unknowable, not when the user tires.
- Load `~/.claude/waypoint/capture-checklists.md` **once**, before writing, as a coverage
  check — it lists probe areas and marks what must be asked. It is not a script.
- Silence is never resolved into a plausible answer.

## Step 4 — Write

`WP init <service>` creates the folder, `waypoint.yaml` and `ledger.md`.

Fill `waypoint.yaml` (≤25 lines, index not documentation). Then write the **default set**:

| Doc | Contains |
| --- | --- |
| `overview.md` | BLUF, responsibility, why it exists separately, neighbours (a flow), where the reference lives, what deliberately isn't here, evidence |
| `architecture.md` | BLUF, guardrails, structure (a flow), interfaces (in + out), runtime, evidence — one doc, not three |
| `known-context.md` | interview truth: history, constraints, fragility, surprises, `## Unknowns` |

Both docs use the explainer design language (BLUF, `orient-flow`, `orient-evidence`): read
`doc-shapes.md` beside this file for the skeletons, and lint each with
`node ~/.claude/skills/explain/lint-explainer.mjs <doc>`. Diagrams are `orient-flow`, never mermaid.

After the BLUF, `architecture.md` opens with a `## Guardrails` list (max ~6) — the constraints someone could
plausibly undo on their own judgement, typed and path-tagged so `wp context --paths` can push
them before the mistake rather than leaving them at line 92 of a doc nobody opens mid-task:

```markdown
- [technical:G1] `retrievalConditions` interval values are MILLISECONDS, not seconds.
  — paths: apps/shopify-connector/src/adapters/shopify
- [contract:G2] Changing a business's mapping is a customer-visible release with no code diff.
  — paths: code/src/import
```

Kinds: `contract` | `policy` | `operational` | `technical`. The cap is the point — nobody deletes
a guardrail, so a long list becomes a wall that gets skipped. If it isn't worth stopping a
sign-off over, it is prose in `known-context.md`, not a guardrail.

In `known-context.md`, mark any claim that is a **dated snapshot of mutable state** rather than
durable truth — `(snapshot 2026-09-04)`. That doc is exempt from commit staleness by design, so
an expiring claim inside it rots invisibly behind what reads as a guarantee; the marker lets
`wp doctor` age it without breaking the exemption.

Add `operations.md` (backend: deploy, observability, real failure modes), `testing.md`
(only when the real strategy isn't obvious from the repo) or `interfaces.md` (only when the
surface is too large for `architecture.md`) when the service justifies it. Omit the rest.
Do not create a doc you'd have to pad.

Every doc gets frontmatter and a **verification anchor**:

```yaml
tags: [waypoint, <service>]
verified: <date>
verified_sha: <short sha>
verified_paths: [src/http, iac]
```

Set them with `WP verify <service> <doc> --paths a,b`. `known-context.md` is exempt from
staleness — leave its paths empty.

Fill `waypoint.yaml`'s `runtime:`/`commands:` blocks too — what to run, from which root, and
which of the org's four gate commands this repo is **missing** (fapi has no `build:check:tests`;
dedupe-service and snap-adapter are Vitest, most are Jest). Anchor it with
`WP verify <service> commands --paths <manifests>` — manifest files only (`package.json`,
`mise.toml`, `go.mod`, …); it refuses a source directory, because an anchor on `src/` fires on
every commit and gets ignored within a week.

Then `WP index` to refresh `Engineering/index.md`.

## Step 5 — Report

Print the files written, the `## Unknowns` list, and one line on what a future agent should
read first. Nothing is committed anywhere; nothing is posted anywhere.

## Asking for input

A modal is a **blocking stop**, so the rule is not "prefer the modal" — it is *only stop where you
were going to stop anyway*.

1. **A sensible default exists → take it and say so.** Don't stop for something you can decide.
   Mentioning a choice while carrying on beats interrupting for it.
2. **You'd stop anyway and the options are knowable → `AskUserQuestion`.** One click beats a
   typed paragraph. Cap: 4 options per question, 2 minimum, 4 questions per call.
3. **Only the user holds the fact → ask in prose.** If you had to invent an option to reach the
   two-option minimum, you are in this case (or in case 1). Never manufacture plausible answers to
   a domain question — an invented option anchors the answer, and "Other" does not undo that.

## Stop conditions

- Repo not found or not a git repo → ask which service is meant.
- The service is a thin wrapper/library with nothing durable to say → say so and write
  `overview.md` + `waypoint.yaml` only.
- The user won't answer the interview → write the inferred docs, mark every uncertain claim,
  and put the unanswered questions under `## Unknowns` rather than guessing.
