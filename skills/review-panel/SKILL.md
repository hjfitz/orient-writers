---
name: review-panel
description: Review any diff (PR number/URL, current branch, working tree, or a path) in any repo with a small panel of Sonnet subagents, each with a different persona — backend, frontend, platform, plus specialist lenses picked from a pot by what the diff touches. Token-frugal - tiny diffs are reviewed inline with no agents, each agent reads only its slice, and findings come back terse and are verified before they're reported. Report-only; nothing is posted unless asked. This is the default for ANY review request (a PR, a branch, "have a look at this", "is this ok") — use it instead of /code-review, /security-review, or an ad hoc read-through.
---

# Review panel

Cheap, parallel, different-eyes review of a diff. The shape follows `waypoint-plan` Step 3: fresh read-only agents launched in one message, each with its own lens, findings only. Repo-agnostic: the repo's own rules come from its `AGENTS.md` / `CLAUDE.md`, not from this file.

Rules that keep it cheap:

- **Spend scales with the diff.** Tiny diffs get no agents. Big diffs get at most **4**.
- **Sonnet only** (`model: "sonnet"`), default effort. Never Opus for a panelist, never Haiku (it misses real bugs).
- **The diff goes to disk once.** Agents read their slice from the file; it is never pasted into a prompt.
- **Agents return ≤5 findings each**, with a file:line and a concrete failure. No summaries, no praise, no restating the diff.
- **You** (the lead) dedupe and verify. Reviewers never talk to each other.

## Step 1 — Resolve the target and get the diff

Target, in order: a PR number/URL the user gave; the PR for the current branch; the working tree's diff against the default branch. More than one candidate → ask. Never guess.

Find the repo from the URL or the cwd's git root. Resolve the base explicitly (`git symbolic-ref --short refs/remotes/origin/HEAD`; if that isn't set, try `origin/main` then `origin/master`) rather than assuming.

```bash
S=<session scratchpad dir>   # or $(mktemp -d)
gh pr diff <n> -R <owner>/<repo> > $S/review.diff             # PR
git -C <repo> diff <base>...HEAD > $S/review.diff             # branch
git -C <repo> diff > $S/review.diff                           # working tree
gh pr view <n> -R <owner>/<repo> --json title,body,files      # intent + file list (PR only)
```

Intent = PR title/body, or the branch's commit messages. Every agent is given it. Generated files (generated API code, lockfiles, `*.gen.*`, snapshots, vendored code) are noise: agents skip them.

Find the repo's house rules once: `AGENTS.md`, then `CLAUDE.md`, at the repo root. Note the path and section names worth reading; don't paste them into prompts.

## Step 2 — Size it, then pick the panel

Count changed lines (`grep -c '^[+-][^+-]' $S/review.diff`, excluding generated files) and bucket the changed paths by what they are, not by repo-specific globs:

| Bucket | Typically |
| --- | --- |
| backend | server-side source (Go, Python, Java, server TS, …), API specs, shared server packages |
| frontend | UI source, components, pages, styles, client-side state and data fetching |
| platform | IaC (Terraform etc.), CI workflows, Dockerfiles, deploy/build config, tool version pins |

Anything that fits none (docs, data, scripts) goes to the nearest bucket by who would care about it.

**Size gate**

- **≤ ~80 changed lines and one bucket → no agents.** Review it yourself through that bucket's persona below and report. This is the common case; don't spawn for it.
- Otherwise: **one agent per bucket touched**. A bucket with only a few lines folds into the nearest persona instead of getting its own.
- Then add **specialists from the pot**, only while the total stays ≤ 4 and the trigger is actually present in the diff:

| Pot persona | Pick when the diff… |
| --- | --- |
| **security** | touches authn/authz, sessions, secrets/env, file upload, untrusted input reaching SQL/shell/templates/paths/URLs, CORS/CSP, IAM |
| **data** | adds or edits migrations, queries, indexes, transactions, or anything retry/duplicate-delivery sensitive (queues, batch jobs, webhooks) |
| **contract** | changes an API spec, a generated client, an event/message schema, or a request/response shape shared between producer and consumer |
| **tests** | adds logic with thin or no test changes, or is mostly tests (are they asserting behaviour?) |
| **ops-script** | changes a script an operator runs against live systems (cutover, migration, runbook, deploy helper): shell with `gcloud`/`kubectl`/`gh`/cloud CLI calls that mutate state |
| **traffic** | changes the live request path: load-balancer backends, health checks, forwarding rules, listeners, DNS records, static IPs, firewall rules on serving ports, autoscaling or rolling-update policy |

If more than 4 qualify, keep the buckets, then the pot personas with the strongest trigger, and say what you dropped. A large single-bucket diff usually gets that bucket's persona plus the best-fitting pot persona.

Tell the user the panel in one line before spawning ("4 agents: backend, frontend, security, contract") and go; don't ask.

## Step 3 — Spawn the panel (one message, parallel)

One `Agent` call per persona, all in a single message: `subagent_type: "general-purpose"`, `model: "sonnet"`, no worktree isolation, **read-only**. Prompt = the shared brief below with the persona block substituted in. Keep prompts short: the lens is the value.

**Shared brief**

```
You are reviewing a diff as the {PERSONA} reviewer. Read-only: do not edit, write, commit or run anything that mutates state.

Repo: {REPO_PATH}   Diff (already on disk, read it): {S}/review.diff
Your files: {YOUR_PATHS} — review only these; skim others only to resolve a reference.
Intent of the change: {TITLE + 2-line summary}
House rules: read {REPO_PATH}/{AGENTS.md or CLAUDE.md}{, section "X" if known} first, and treat what it says as the standard. If it has no rules for your area, say so and apply only your lens.
Skip generated code, lockfiles and vendored code. Read surrounding source narrowly (offset/limit), not whole files.

Report at most 5 findings, most severe first. Only things that are wrong or break a house rule in THIS diff — not style a linter owns, not naming taste, not hypotheticals, not refactors. For each:
  file:line — one-sentence defect — the concrete input/state that makes it fail — confidence (high/med)
If something needs a product or domain decision, write "QUESTION:" and ask it. If you find nothing, return exactly "no findings". No preamble, no summary.

Your lens: {PERSONA BLOCK}
```

**Persona blocks** (language-neutral; the repo's house rules supply the stack specifics)

- **backend** — Layering and dependency direction as the repo defines it; business rules in the wrong layer (handlers, adapters); framework/SDK types leaking into core logic. Error handling: errors translated at boundaries, expected outcomes not modelled as exceptions, nothing swallowed. Retry safety and idempotency (write-then-publish ordering, partial failure finishing on retry). Dependencies injected, not constructed inline (clock, IDs, clients). Concurrency, resource and context leaks, nil/null/zero-value traps. Logs carry identifiers, never payloads or secrets. Config read only where the repo says it may be.
- **frontend** — Follow whatever the repo's rules say about UI structure, component libraries and state/data-fetching; if they're silent, don't invent rules or impose backend layering. Check: server/client boundary mistakes, missing loading/error/empty states, effects with wrong dependencies, unhandled promise rejections, accessibility breakage (labels, focus, keyboard), server-only values or secrets reaching the client, response shapes assumed instead of taken from the typed client.
- **platform** — Terraform/IaC: destructive or replace-forcing changes, IAM broader than needed, environment/state separation, secrets in plain config, missing deletion protection on stateful resources. CI: unpinned actions, secrets exposed to untrusted PRs, missing `permissions:`, deploy gating bypassed, path filters that skip jobs they shouldn't. Docker: root user, build-time secrets, layer-order cache busting. Anything that changes the deploy or rollback story.
- **security** — Trust boundaries first: where does untrusted input enter and what does it reach (SQL, shell, filesystem paths, templates, redirects, outbound URLs → SSRF)? Authn/authz on every new route, tenant/customer scoping on every query, secrets and PII in logs/errors/responses, upload limits and types, CORS/CSP/cookie flags, IAM least privilege. Report only with a plausible exploit path, and state it.
- **data** — Migrations: lock and long-run risk, backfill, reversibility, ordering with deploys (old and new code must both run against the schema in between). Queries: missing index for the new access pattern, N+1, unbounded results, wrong transaction boundaries, timestamps and timezones. Duplicate delivery and idempotency on any consumer or batch path.
- **contract** — Spec vs handler vs generated code vs client: do they agree? Breaking changes for existing callers (removed/renamed/now-required fields, changed status codes or enums), generated files regenerated and committed, error shapes consistent, pagination and nullability conventions followed, event/message schemas versioned or additive.
- **tests** — For each new behaviour or fixed bug: is there a test that would fail without the change? Do tests assert observable behaviour (return value, response, emitted message) rather than implementation? One behaviour per test where the repo says so; real stores for repository changes where the repo does that. Report missing failure-path coverage, not coverage percentages.
- **ops-script** — The script will run once, against production, with someone watching. Check: does a failed read count as "absent" and trigger a mutation; is every step resumable after a crash between two mutations (and is the resume detected from live state, not a local file); do dry-run and `--apply` take the same path apart from the mutating calls; are refusal guards checked before the first mutation; does `set -euo pipefail` actually stop on failures in pipelines, `$(...)` inside conditions, `local x=$(...)` and `|| true`; quoting and word-splitting of names and IDs; timeouts and polling with an upper bound; the message on failure telling the operator exactly what state they're in and what to do next. New env-specific branches (dev vs prod) should be exercised by a test or a dry run.
- **traffic** — What happens to a live connection during and after the change. Check: can a backend, health check or forwarding-rule change send traffic to something not ready (health check probing the wrong port or process, probe source ranges missing from the firewall); does a replace-forcing field drop an IP or listener; session affinity and connection draining on backend changes; ordering against other applies that touch the same resources; rollback is the reverse change and doesn't itself need a replace; the blast radius when the change applies while customers are connected. State the customer-visible effect of each finding.

## Step 4 — Verify and synthesise (lead, you)

1. **Merge duplicates** across personas (same file:line or same defect); keep the sharpest wording, and note who else saw it only if it raises confidence.
2. **Verify every high-severity finding** by reading the cited lines yourself (`Read` with offset/limit, never the whole file). A finding whose failure scenario doesn't survive that is dropped, not softened. Medium-confidence findings you can't cheaply verify go in a separate "unverified" list.
3. **Drop** linter-owned style, naming taste, hypotheticals not in the diff, and "while you're here". A QUESTION line is kept and surfaced as a question, not a finding.
4. **Don't pad.** Zero surviving findings is a valid and good result.

## Step 5 — Report

In the terminal, terse. No re-posting of the diff, no per-agent transcripts.

```
Panel: backend, frontend, security (N changed lines)
Verdict: <Looks good | Changes needed | Needs a decision>

Blocking
- path:line — defect. Fails when …. (backend, security)

Unverified (read before trusting)
- path:line — …

Questions
- …
```

The panel never posts. If the user wants it on the PR, post it following that repo's own review conventions (for Fuse, the `review-code` skill's: binary Approve / Request changes, inline comments each prefixed `[blocking]`, one finding per comment). Offer that in one line; don't do it unprompted.

## Stop conditions

- The target doesn't resolve to exactly one diff.
- The diff is huge (> ~1500 changed lines excluding generated files): say it's too big to review credibly and suggest splitting, rather than fanning out agents over it.
- A finding needs product/domain judgement: surface it as a question.
- Any agent reports it was asked to or did mutate something: stop and tell the user.

## Tuning

The value is in the persona blocks. When a persona keeps producing findings you drop in Step 4, tighten it; when a real bug slipped through, add the missing check to the closest persona. Add to the pot only if a trigger in the diff can pick the persona mechanically.
