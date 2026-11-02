---
name: waypoint-test
description: Run a focused verification pass against intended behaviour — select checks from acceptance criteria, implementation risk, affected boundaries and known failure modes, gather real evidence, and feed findings back into the Waypoint plan. Usable standalone when the user wants work scrutinised or verified rather than a suite run. Trigger when the user asks to test/verify/scrutinise a change or a waypoint, or asks whether the work is actually correct.
---

# Waypoint — test

Verification, not ritual. `WP = python3 ~/.claude/waypoint/wp.py`

**A green suite is not a correct change.** The job is to establish that the intended
behaviour actually holds, and to name what remains unverified.

## Step 0 — Orient

With a plan: `WP context <service> --plan <stem>` (the plan's file stem; a bare ticket works
because stems start with it) — acceptance criteria and the
increment's stated verification are the target, plus any `## Learnings` candidate the plan
raised: confirming or refuting those is part of this pass, not optional extra credit.
Without a plan: ask what to scrutinise — an open question, in prose, since the answer is whatever
is on their mind and not a set you can enumerate — then establish the change from `git diff --stat`
against the base branch.

## Step 1 — Select the checks

Derive them, in this order of authority:

1. **Acceptance criteria** — every one needs evidence, or an explicit "not verified".
2. **Implementation risk** — what in this diff is most likely to be wrong.
3. **Affected boundaries** — contracts, envelopes, subscriptions, routes, UI flows.
4. **Known failure modes** — open `known-context.md` / `operations.md` for the boundaries this
   diff touches and actively try to reproduce each documented failure mode against the diff,
   rather than just noting the doc exists. A failure mode that was true before this change and
   is untested after it is a gap, not a pass.

Load `~/.claude/waypoint/verification-menu.md` only when the right checks aren't already
obvious — it's a menu keyed by `type: backend|frontend` from `waypoint.yaml`, not a checklist.
Never apply frontend checks to a backend service or vice versa.

## Step 2 — Verify

- Run the narrowest sufficient checks; prefer evidence a human can re-run.
- Add tests where coverage is genuinely missing, following the repo's testing conventions
  (one behaviour per test).
- Exercise failure paths, not just happy paths, when the change created one.
- For anything visual, capture a screenshot; for anything operational, a log or metric query.
- If a check can't be run here (needs a deployed environment, a real customer file, a human
  in a UI), say so plainly and name what the human must do.

## Step 3 — Feed back

Write findings into the plan's `## Verification` section, which is the **single authority** for
evidence — increment lines carry `— done: <sha>` and nothing else. It has two subsections:

- `### Evidence` — newest first, **dated**, one bullet per check actually run, opening with what
  it discharges: `- 2026-09-04 [inc 3] deployed to dev, posted a mismatched-source confirmation
  for PURDYFIGG; connector_unresolvable published, correlation-id 4f2a…`. Sign-off requires at
  least one dated bullet here, so "suite green" alone will not clear it.
- `### Not verified` — stated, not papered over. `(none)` is a deliberate claim and a fine one.

Two plans in the vault currently contradict themselves (a Verification section reading "no
increments executed yet" above six ticked increments), which is what happens when evidence is
written in two places with no precedence rule. Then:

- A failure becomes an unchecked increment in the plan, not a footnote.
- Never tick an increment you couldn't verify.
- If the finding invalidates the plan's approach, say so — that's a re-plan, not a fix.
- Resolve any open `## Learnings` candidate this pass touched — mark it confirmed, refuted, or
  say plainly why it's still open. Don't leave it hanging for sign-off to guess at. A newly
  surfaced durable fact from this pass goes into `## Learnings` too, same as planning/work.

Report to the user as: verified / not verified / needs a human. No padding.

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

- Nothing to verify yet (no diff, no plan) → say so.
- Verification needs production access or a live customer action → hand it back with the exact
  steps rather than approximating it.
- The change looks correct but untestable as built → report that as a finding.
