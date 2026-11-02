---
name: customer-list
description: Show every customer captured in the Fuse Customers vault, one line each, flagging any whose captured config facts have never been synced or are stale against live config-service. Read-only, no state changes. Trigger when the user asks what customers are captured, which businesses have known nuance documented, or wants a list of Fuse Customers vault entries.
---

# Customers — list

Reporting only. No writes, no state changes. `CUST = python3 ~/.claude/customers/cust.py`

## Step 0 — Pull the list

```
CUST list
```

Every onboarded business, one line: businessId, friendly name, connector count, sync freshness
flag (`ok` / `STALE:<n>d` / `NEVER SYNCED`).

## Step 1 — Present

- Don't summarize into prose. A scannable list/table is the deliverable — `cust list` already
  gives you the shape, don't re-sort it by recency or business name.
- Surface every `STALE` or `NEVER SYNCED` flag prominently — a customer whose captured retrieval
  conditions/mapping facts haven't been checked against live config-service in a while is the one
  finding worth calling out unprompted, not a footnote.
- Say the total count up front (e.g. "4 customers captured, 1 stale").

## Rules

- Never onboard a new customer, sync one, or edit a doc from this skill — hand off to
  `customer-onboard`/`customer-sync` if the user wants to act on something this surfaces.
- This is an index of *what's captured*, not a business directory — a customer with no vault
  folder isn't "missing," it just hasn't needed a `customer-onboard` pass yet. Don't imply
  every live business should have one.

## Stop conditions

- `~/Documents/obsidian/Customers` doesn't exist yet, or is empty → say so plainly ("nothing
  captured yet"), point at `customer-onboard`, don't pad the report.
