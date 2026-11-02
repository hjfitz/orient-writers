---
name: waypoint-plan
description: Turn a ticket, bug, feature or refactor into an executable Waypoint plan stored in the Obsidian vault — orient from the service index, establish intent with the user, draft the implementation via a dedicated planning agent, then adversarially review it across three independent dimensions (documented history, factual grounding, increment structure) before writing the plan that survives a session boundary. Trigger when the user asks to plan a ticket or piece of work, or says "waypoint this".
---

# Waypoint — plan

One ticket, one plan file, in the vault. `WP = python3 ~/.claude/waypoint/wp.py`

Drafting and reviewing happen in agents separate from this session, deliberately: a plan written
and pressure-tested by the same mind inherits that mind's blind spots. Splitting them is what
catches the gaps a single self-checking pass misses.

## Step 0 — Orient cheaply

`WP context <service>` — index, doc staleness, explainer theses, recent ledger headers.

If it reports `onboarded: NO`, **ask the user whether to onboard first** (`waypoint-onboard`).
Don't decide alone, and don't halt: if they decline, proceed from source and say the plan is
running without durable context.

Load a durable doc only for a named reason. Never the whole ledger.

If `context` lists an existing `draft` plan matching what the user wants to work on, check
its `## Intent` before starting fresh — a `ticket: none` draft with an Intent already filled
is a **waypoint-ideate stub**, not a half-finished plan of yours. Continue from Step 1 using
that Intent as the starting brief in place of a ticket, and fill in a real `ticket:` in the
frontmatter only if one gets created for it along the way.

## Step 1 — Establish intent

Read the ticket (`mcp__Atlassian__getJiraIssue` for `FUSE-*`). Restate in your own words:
the change, and the observable outcome that proves it. If acceptance criteria are thin or
the ticket contradicts the code, ask — one round, specific questions.

No ticket, working from an idea stub instead? Treat its `## Intent` (and the matching
`ideas-log.md` entry, for the fuller rationale) as the brief — same bar applies: if it's thin
or the idea turns out stale against current code, ask before writing increments around it.

## Step 1.5 — Model check (planning)

Now the intent is known, size the *planning* work against `~/.claude/waypoint/model-routing.md` —
which owns the tiers, the detection, and the halt rule — and check the model you're running on. In
short: an architectural or cross-service change is `opus/high`; a bounded single-service plan is
`sonnet/medium`; a mechanical one is `haiku/low`. Read your current model from your own session
identity (Opus/Sonnet/Haiku → tier).

**If you're under the recommended tier, halt here** — before spending on the Step 2/3 agents, which
are only as good as the model directing them. Tell the user what tier this needs and why, and
`AskUserQuestion`: switch model now / proceed anyway / adjust the recommendation. Over-powered gets a
one-line note and carries on; effort is stated, not gated (you can't read your own). This is the
first hard gate in the skill.

## Step 2 — Draft via the planning agent

Spawn a fresh `Plan`-type agent (`subagent_type: "Plan"`) — the same agent Claude Code's own
plan mode uses — with a self-contained brief. It has no access to this conversation, so include:

- The established intent (Step 1), in full.
- The repo location to inspect: the worktree path if one already exists for this ticket, else
  the checkout path from `WP context`'s service info.
- The service's `key_paths` (from `waypoint.yaml`) as a starting point, not a boundary — let it
  follow the code where it actually leads.
- An explicit ask for: the critical files/boundaries touched, a numbered sequence of
  independently implementable-and-verifiable increments, and the trade-offs it considered.

Deliberately **do not** hand it `known-context.md`, the ledger, or explainers. This agent's value
is a clean architectural read of the problem, unbiased by the vault's own history — that
cross-check belongs to Step 3, not this one.

## Step 3 — Adversarial review (three parallel dimensions)

Launch three fresh, independent agents **in parallel, in one message** — none shares context
with the writer or with each other, and none may edit anything (source, plan, or vault):

1. **History & context** — open `known-context.md` in full (not the header) and grep `ledger.md`
   for prior entries touching the same paths. Cross-check every increment and assumption in the
   draft: has this area burned someone before, is a documented constraint at risk, does the draft
   contradict something already known? For each explainer covering an affected boundary, read the
   mechanism, not just its thesis line. If `WP context` flagged a doc `STALE`, this is where it
   gets resolved — check it against source and say whether it still holds.
2. **Factual grounding** — verify every file, function, type and boundary the draft names
   actually exists and behaves as described, by reading the real source directly. Flag anything
   invented, renamed, or drifted since the draft was written.
3. **Increment structure** — is each increment independently implementable *and* verifiable, with
   real verification namable inline? Is any increment secretly two? Is the total count sane
   (prefer 3-7 — more means the ticket is too big, say so explicitly)?

Each reports findings only, terse: what's wrong, where, and — if mechanical — the fix. Anything
that's a genuine product/domain question gets flagged as one rather than guessed at.

## Step 4 — Resolve findings and write the plan

Fold the three reviews into the draft:

- **Factual-grounding fixes** — apply directly; they're not judgment calls.
- **Contradictions with documented history** — resolve explicitly: either the plan changes, or
  you're knowingly overriding documented history — say which, and why, in the plan itself.
- **Increment-structure fixes** — restructure as flagged.
- **Genuine ambiguity any reviewer surfaced** — raise with the user now, **in prose, never as an
  `AskUserQuestion`**. Only they hold the answer, so options would be your guesses at it, and a
  guessed option anchors the reply. Don't invent an answer, and don't invent a menu of them.
- Anything true and durable that surfaced and **isn't written down anywhere yet** is a candidate
  learning — carry it into `## Learnings`, even if it didn't change the plan.

Then:

```
WP plan new <service> --ticket FUSE-123 --title "short title"
```

Run it **from the worktree** — it stamps repo, branch, base (origin's default branch) and base
sha into the plan, which is what lets a new session resume without archaeology. It warns and
stamps `unknown` if the cwd isn't a checkout of that service's repo; fix the frontmatter rather
than leaving `unknown` in place. For work with **no code change** (a prod config sweep, deploy
sequencing) add `--config-only` so `branch`/`worktree` are stamped `none` and sign-off gates on
Verification, increments and acceptance criteria instead of demanding a diff. Fill the template
from the now-corrected draft:

- **Intent** — 2-4 sentences.
- **Acceptance criteria** — observable outcomes, not tasks.
- **Affected boundaries** — components, contracts, paths; wikilink explainers.
- **Assumptions & uncertainty** — each with how it was established. Genuine product/domain
  questions go here as `UNRESOLVED:` and are raised with the user, not invented.
- **Increments** — each independently implementable *and* verifiable, with its verification
  named inline, and citing the criteria it discharges as `(AC 2,4)`. A precondition that is
  **not code** (another ticket reaching prod, a monitor reading real volume) goes on its own
  indented `gate:` line with a `[ ] confirmed` box — sign-off blocks on a ticked increment above
  an unconfirmed gate, which is the difference between a warning and a mechanism.
- **Verification** — left for `waypoint-test`/`work` to fill with real evidence, under
  `### Evidence` (dated bullets) and `### Not verified`.
- **On-demand sections** — the default template is deliberately 8 headings. Add
  `WP plan add-section <service> --plan <stem> rollout` when the change has deploy ordering,
  flags, one-way doors, or touches shared state git does not own (a dev deploy, a prod config
  write, a Datadog monitor, a CI var, cross-repo IaC); add `... options` when the Step 2/3 work
  surfaced alternatives worth recording. Don't add either speculatively.
- **Learnings** — candidates surfaced in Step 3. Write `(none)` if genuinely nothing new; don't
  pad it to look thorough.

Then record the **recommended implementation model**. Now the increments exist, size the
*implementation* against `~/.claude/waypoint/model-routing.md` — a different axis from Step 1.5, since
a change can be hard to plan but mechanical to build, or the reverse. Record it:

```
WP plan set-model <service> --plan <stem> --model <opus|sonnet|haiku> --effort <low|medium|high>
```

It rides in the plan frontmatter, shows on `wp brief`'s `MODEL` line, and orient chips it on the plan —
so the session that picks this up (Step 1 of `waypoint-work`) can gate on it. State the tier and the
one-line why to the user in prose.

Size discipline: a plan is a working document, not a design doc. Every paragraph should be
something *only this plan* can say — if it restates source, an explainer or a durable doc, cut it
and link instead. (There is deliberately no word count: the old ~400-word cap was violated by
every plan in the vault, by 3.6x to 14.7x, and a rule nobody keeps discredits the ones next to it.)

## Step 5 — Agree and activate

Show the plan (or its diff, if amending). Corrections come back as prose — they are free-form and
must not be squeezed into options. Once there are none, the activate/hold decision *is* a closed
one: `AskUserQuestion` — activate it now / leave it `draft` for later / amend something specific
first. Then `WP plan set-status <service> --plan <id> --status active`.

## Rules

- The plan is living. Amending it later is correct behaviour, not a failure.
- No speculative implementation detail where a file read settles it.
- Step 3's three reviews are not optional for a non-trivial change. Step 0 is index-level and
  cannot tell you nothing's relevant — only actually reading `known-context.md` and the ledger
  (the history reviewer's job) can.
- Don't create explainers or touch durable docs here. That's sign-off's job — Learnings are
  candidates you hand off, never a write you make yourself.
- None of the Step 2/3 agents may edit the vault, the plan file, or source — they draft and
  report; this session is the only one that writes.

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

- The work spans several services → one plan per service, each with its own file, cross-linked.
- The "ticket" is really an investigation with no known outcome → say so; use `waypoint-test`
  or plain investigation first, then plan.
- Product/domain intent is genuinely ambiguous → surface it and stop at `draft`.
- The history-review dimension surfaces a contradiction with documented history that can't be
  reconciled by adjusting the plan → stop, surface it, don't quietly override documented history.
