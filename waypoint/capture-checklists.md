# Onboarding capture checklists

**Loaded only by `waypoint-onboard`, and only as a coverage check before writing.**
Not a questionnaire — never walk a user through these. Use them once, after
inspection, to notice what your provisional model is silently missing.

Most items are answerable from source. Only the ones a repo cannot answer are
interview material; those are marked **(ask)**.

## Backend

- responsibility and boundary — what this owns, and what deliberately isn't here **(ask)**
- ingress: HTTP routes, Pub/Sub subscriptions (and their `filter`s), cron, SFTP, webhooks
- egress: which services/systems it calls, and what it publishes
- persistence: stores, collections/tables, ownership vs read-only access
- async boundaries: what is fire-and-forget, what is awaited, what is ordered
- retry / idempotency: who retries, what makes a replay safe, where dedupe lives
- auth: inbound (who may call) and outbound (how it authenticates)
- runtime and deploy: platform, region, scaling, gates, promotion path
- observability: metrics/log conventions, dashboards, monitors that matter
- failure modes: what actually breaks in practice, and how it shows up **(ask)**
- operational/business constraints on external dependencies — vendor quirks,
  rate limits, contractual behaviour **(ask)**

## Frontend

- product responsibility — what this app is for, who uses it **(ask)**
- routing: structure, dynamic segments, auth-gated areas
- rendering model: server/client boundaries, streaming, caching
- state: server state vs client state, which library, what is deliberately not global
- data fetching: client, error/loading conventions, revalidation
- component/design system: source of primitives, what may not be hand-rolled
- forms and validation: library, schema location, server-side revalidation
- auth/session: provider, token lifetime, refresh, what happens on expiry
- analytics and feature flags: what is instrumented, who reads it
- accessibility expectations — what is actually enforced vs aspirational **(ask)**
- contractual UX behaviour — behaviour users or the business depend on that a
  refactor must not change **(ask)**
- deploy/runtime: platform, preview environments, env var surface

## Interview probes (adapt; never recite)

Ask only where inspection left a real gap:

- What is this service actually responsible for, in one sentence?
- Why does it exist separately from <the thing it looks closest to>?
- What deliberately does not belong here?
- Which decisions here would surprise someone reading only the source?
- Which parts are fragile, and what makes them fragile?
- What tends to bite new engineers here?
- Which external dependency has an unusual operational or business constraint?
- Which boundaries are intentional rather than accidental?
- (frontend) Which UX behaviours are effectively contractual?

## Writing rules

- Interview answers go in `known-context.md` — that is the only doc whose content
  cannot be re-derived from source, so it is the most valuable file you write.
- Never resolve silence into a plausible answer. Unanswered questions are written
  verbatim under `## Unknowns`.
- Anything trivially rediscoverable from source (file lists, dependency versions,
  function signatures, route tables that change weekly) does not go in a doc.
  Point at the path instead.
