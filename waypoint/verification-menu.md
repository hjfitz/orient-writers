# Verification menu

**Loaded only by `waypoint-test`, and only when the right checks aren't already
obvious from the plan.** A menu to select from — never a checklist to complete.

Select by: acceptance criterion → implementation risk → affected boundary →
known failure mode. If an item maps to none of those, skip it.

## Backend

| Check | Reach for it when |
| --- | --- |
| unit | pure logic, mapping, validation, branching |
| integration | crosses a boundary the unit test stubs (db, http client, cache) |
| contract / schema | an envelope, canonical type or API shape changed |
| message/event behaviour | publishes, attributes, subscription filters, ordering |
| failure behaviour | a new error path, a 4xx/5xx classification, a timeout |
| retry / idempotency | the change can be replayed, or dedupes, or holds records |
| observability | a metric/log/monitor is part of the deliverable |
| load / performance | the change is on a hot path or fans out |

## Frontend

| Check | Reach for it when |
| --- | --- |
| unit | pure helpers, formatting, reducers, hooks in isolation |
| component | rendering, props/state behaviour, conditional UI |
| integration / E2E | a user-visible flow crosses pages or auth |
| visual | layout or design-system usage changed (screenshot evidence) |
| accessibility | interactive markup, focus order, labels, keyboard paths |
| responsive | layout differs by breakpoint |
| API loading/error states | a fetch was added or its failure path changed |
| interaction | drag/drop, keyboard, optimistic updates |

## Evidence standards

- Prefer evidence a human can re-run: a command with its output, a log query, a
  request/response pair, a screenshot for anything visual.
- Name what you did **not** verify. An unverified acceptance criterion is a finding,
  not an omission.
- A passing suite that does not touch the changed path is not evidence. Say so.
