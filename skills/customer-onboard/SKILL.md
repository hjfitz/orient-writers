---
name: customer-onboard
description: Build durable customer-facing context for one Fuse business in the Obsidian vault — pull live config-service state first, form a provisional model, then interview the user only about what config-service cannot answer (contract context, contacts, upcoming changes), and write a small set of high-signal docs plus a tiny machine-readable index. Trigger when the user asks to onboard a customer/business into the Customers vault, capture nuance about a customer, or when customer-sync/customer-list finds a business that has no vault folder.
---

# Customers — onboard

One business, once. Everything lands in `~/Documents/obsidian/Customers/<BUSINESSID>/`.

This is the customer-facing counterpart to Waypoint (`waypoint-onboard`): Waypoint captures why a
**service** is shaped the way it is; this captures why **one customer's config** is shaped the
way it is, and what broke because of it. Same discipline, different axis — a retrieval-condition
race or a mapping quirk that's specific to one business doesn't belong in a service's
`known-context.md` (it would drown genuinely service-wide facts); it belongs here.

`CUST = python3 ~/.claude/customers/cust.py`

## Step 0 — Locate

`CUST locate <businessId>` (businessId is whatever config-service uses, e.g. `PURDYFIGG` — case
is normalised to upper). If it reports `onboarded: true`, do **not** rewrite: hand off to
`customer-sync` instead and report what it finds drifted.

## Step 1 — Inspect (read-only, live config first)

Pull the live picture before asking the user anything:

- `mcp__fuse__list-customers` (to confirm the business exists and get its friendly name) and
  `mcp__fuse__get-business-config` / `mcp__fuse__config-read` for backend + connector(s) +
  retrieval conditions + active mappings
- `mcp__fuse__dedupe-summary` and `mcp__fuse__replay-list-failures` for a recent-health signal
  worth noting (a live failure-inbox backlog, an unusually high dedupe-blocked count)
- Search the vault for existing scattered notes on this customer — `Bifrost/`, `Explainers/`,
  `People/` pages, anything under the business's name — and **fold them in by reference**
  (link, don't duplicate). This is common: customer nuance tends to already exist somewhere as an
  ad hoc note from onboarding/testing before this vault space existed.
- Fuse MCP `trace-data-flow` / `lookup-config` if the customer's use-case mix isn't obvious from
  its connector config alone

## Step 2 — Provisional model (in chat, not a file)

Post a compact bulleted model — channels/integrations, retrieval/mapping gating that's
non-default, what's on/off (confirmations, outbound tags, stock adjustments), any live health
signal worth flagging. Confidence-tag anything inferred rather than read. Keep it under ~20 lines.

## Step 3 — Interview the gaps

Only what config-service and the vault search couldn't answer — commercial/contract context, who
the actual contacts are, upstream systems (an ERP/subscription platform feeding Shopify, say) and
their own quirks (batch timing, release delays) that explain config decisions but aren't
themselves in Fuse's config.

- Never ask what `config-read`/the vault search already answered.
- State your best guess inside each question so the user confirms or corrects.
- `AskUserQuestion`, batches of ≤4, max two rounds. Stop when remaining gaps are genuinely
  unknowable, not when the user tires.
- Silence is never resolved into a plausible answer — put it under `## Unknowns` instead.

## Step 4 — Write

`CUST init <businessId> --friendly-name "..." --environment production`. Fill `customer.yaml`
(connectors, backendId, warehouse, `wms:` — a list, since a customer can eventually split across
more than one WMS — index, not documentation). Then write:

| Doc | When | Contains |
| --- | --- | --- |
| `overview.md` | always | who they are, integration shape, non-default gating, links to onboarding ticket/pre-existing notes |
| `architecture.md` | always | a mermaid diagram — upstream system(s) → channel(s) → connector(s) → WMS(es), plus the confirmation/egress path back. Collapse Fuse's own internal pipeline (collector/dedupe/the WMS adapter) to **one box** — that's Waypoint's job per-service, not this customer's; what earns a place here is what's customer-specific (which channel feeds which connector, which connector writes to which WMS). This is the doc that makes a future multi-WMS split visible at a glance instead of buried in `customer.yaml`. Verify the confirmation-egress hop against `mcp__fuse__trace-data-flow` rather than Datadog service tags alone — a shared internal service can be tagged under a different name than its repo (found this the hard way: `fapi` logs as `service:rest_connector`), and unfiltered legacy topics fan out to every connector-type subscriber whether or not that business actually uses it — don't mistake a polite no-op for a second real channel. |
| `known-context.md` | when there's real nuance | incidents, config decisions and why, a `## Captured Config` table of the fields worth tracking for drift, `## Unknowns` |

A business with no real nuance yet still gets `overview.md` + `architecture.md` — the diagram is
knowable and worth having even for the simplest single-channel, single-WMS customer. Only
`known-context.md` is conditional; don't pad one that would just restate `customer.yaml`.

Frontmatter: `tags: [customer, <businessId>]`, `verified: <date>` — there's no git sha to anchor
to (a customer isn't a repo); freshness is tracked by `last_synced` in `customer.yaml`, which
`customer-sync` stamps after it actually reconciles the `## Captured Config` table against live
state. Onboarding itself counts as a sync — after writing, run `CUST synced <businessId>`.

Then `CUST index` to refresh `Customers/index.md`.

## Step 5 — Report

Print the files written, the `## Unknowns` list, and one line on what a future agent should read
first. Nothing is committed anywhere; nothing is posted anywhere.

## Stop conditions

- Business not found via `list-customers` in either environment → ask which business is meant;
  don't guess a businessId.
- Nothing non-default about this customer's config and no incident history → say so, write
  `overview.md` + `customer.yaml` only, and say plainly that a `known-context.md` isn't earned
  yet.
- The user won't answer the interview → write the inferred docs, mark uncertain claims, and put
  unanswered questions under `## Unknowns` rather than guessing.

## Config snapshot

`cust sync` already writes `config.snapshot.yaml` and a generated `overview.md` (marked
`generated: config-snapshot`) for every business. Onboarding a customer means replacing that stub with
hand-written narrative: delete the `generated:` line when you edit `overview.md`, and `cust sync` will
never touch it again. Config facts belong in the snapshot, not in prose.
