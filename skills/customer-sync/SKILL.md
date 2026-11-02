---
name: customer-sync
description: Re-fetch a Fuse customer's live config-service state and diff it against the `## Captured Config` table in that customer's known-context.md, reporting drift plainly before updating anything. This is the staleness-repair counterpart to Waypoint's `wp stale`/`wp verify`, but config-anchored rather than git-anchored — there's no commit history for a customer, only live config-service truth. Trigger when the user asks to sync/refresh/re-verify a customer's captured config, or when customer-list/customer-onboard flags a business as stale or never synced.
---

# Customers — sync

`CUST = python3 ~/.claude/customers/cust.py`

Unlike Waypoint's doc staleness (a git-sha diff against `verified_paths`), a customer has no
commit history — the only source of truth is live config-service. This skill's whole job is
re-fetching that truth and diffing it against what's written down, out loud, before touching
anything.

## Step 0 — Orient

```
CUST context <businessId>
```

Not onboarded → stop, point at `customer-onboard`, don't proceed with a partial sync.

## Step 1 — Read what's captured

Open `known-context.md` in full and pull its `## Captured Config` table — the specific fields
someone decided were worth tracking for drift (retrieval conditions, `confirmationsEnabled`,
`outboundTagsEnabled`, active mappings, whatever that customer's table actually lists). Don't
assume every customer tracks the same fields — read the table, don't guess it from PURDYFIGG's
shape.

## Step 2 — Pull live state

Run `cust sync` first (optionally `--only <businessId>`). It reads live config-service for every
business in prod and dev, writes the secret-free `Customers/<ID>/config.snapshot.yaml`, and logs what
changed since the last run under `changes:`. Read the diff there; the manual per-field pull below is
only for fields the snapshot does not carry (mapping bodies, warehouse routing, backend credentials).

For each connector in `customer.yaml`, call `mcp__fuse__config-read` (or `lookup-config` /
`get-business-config`) for the same fields. Use **production** unless `customer.yaml`'s
`environment` says otherwise.

## Step 3 — Diff, out loud

Present a plain table: field | captured | live | changed?. This is the deliverable of the whole
skill — don't fold it into prose, and don't silently "helpfully" update the doc before showing
the diff.

- No drift at all → say so, still stamp the sync (Step 4) — a confirmed-current customer's clock
  should reset too, that's the point of `last_synced`.
- Drift found → ask whether it's an intentional change worth a ledger entry (a real decision, an
  incident) or just the doc catching up to a change made elsewhere. Either way the doc gets
  updated; only the drift **worth remembering** earns a `CUST ledger` entry.

## Step 4 — Write

Update the `## Captured Config` table to match live state and bump its `verified` date. If the
drift is a real decision or incident (not routine catch-up), add a ledger entry via
`CUST ledger <businessId> --title "..."` describing what changed and why — future-you re-reading
`known-context.md` should never have to guess why a value changed.

Then:

```
CUST synced <businessId>
```

## Stop conditions

- Business not onboarded → hand off to `customer-onboard`, don't partially sync.
- `known-context.md` has no `## Captured Config` table at all → nothing to diff against; say so
  and suggest a `customer-onboard` pass to establish one, rather than inventing fields to track.
- config-service is unreachable → report that plainly; don't stamp `last_synced` on a sync that
  didn't actually happen.
