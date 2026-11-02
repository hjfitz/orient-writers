# Waypoint — model routing

Pick the model + effort a piece of work actually warrants, and stop before planning or implementing
on a model too weak for it. Referenced by `waypoint-plan` (planning-time) and `waypoint-work`
(implementation-time). One rubric, so the two skills can't drift.

## Tiers (capability, version-agnostic)

Reason about tiers, not model IDs — a tier survives Opus 5 → 6 without a rewrite.

- **opus** — the hardest reasoning. A cross-service or architectural change; a canonical-type,
  shared-package or event-contract change with fan-out; novel or genuinely ambiguous design;
  security-sensitive work; anything where a wrong call is expensive or hard to reverse.
- **sonnet** — the default working tier. A bounded change in one service with a pattern to follow;
  a moderate refactor; a feature whose shape is already understood.
- **haiku** — mechanical, low-ambiguity. A dependency bump, a config or doc tweak, a repetitive
  edit across files against a known template, a copy change.

Ordering for the halt below: **haiku < sonnet < opus**.

## Effort (reasoning budget)

- **high** — novel design, many interacting constraints, or increments that aren't obvious.
- **medium** — a known pattern that still needs real judgement.
- **low** — mechanical.

## Two applications — assess each on its own axis

Planning difficulty and implementation difficulty are **not** the same thing. A change can be hard to
*plan* — getting the boundaries and increments right needs opus/high — yet mechanical to *implement*
once the plan exists (sonnet/low), or the reverse. Size them separately:

- **Planning tier** — what does getting the plan *right* need? `waypoint-plan` uses this to gate the
  current session before it spends on the drafting and review agents.
- **Implementation tier** — what does executing the finished plan need? Recorded on the plan as
  `impl_model` / `impl_effort` (via `wp plan set-model`), surfaced by `wp brief` and orient, and used
  by `waypoint-work` to gate the session that picks the plan up.

## Detecting the current model

Read it from your own session identity — your system context names the model you are running as
(e.g. "Opus 4.8"). Map the family to a tier: **Opus → opus, Sonnet → sonnet, Haiku → haiku**.
Fable 5.1 (Mythos-class) sits above Opus: **Fable → opus tier**, so it clears every planning and implementation gate. (Earlier Fable builds were design-only; that note no longer applies.)

You are **not** told your own effort/thinking level. So effort is a recommendation you *state*, never
something you can hard-gate on: say "this warrants high effort," don't claim to have verified it.

## The halt — under-powered only

Compare the current tier to the recommended tier for the task in hand:

- **current < recommended (under-powered) → HALT.** This is the real quality risk. Say what tier the
  work needs and why, tell the user to switch (`/model opus`, and set the recommended effort), then
  `AskUserQuestion`: *switch now / proceed anyway / adjust the recommendation*. Don't plan or
  implement badly on a model too weak for the work — that is the whole point of routing.
- **current ≥ recommended → proceed.** If notably over-powered (opus for a doc tweak), note it in one
  line and carry on. Over-powered is a cost, not a risk, and not worth a stop.

Fast mode (Opus with faster output) is orthogonal to tier — fine for lower-effort opus work, and it
doesn't change the recommendation.
