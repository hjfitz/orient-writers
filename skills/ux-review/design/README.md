# Design language — the project layer

`rubric.md` is the **universal bar**: the dimensions any UI is held against, and the craft
anchors. It is deliberately house-style-agnostic.

The **project layer** is what a given app actually *is* — its tokens, type scale, component
idioms, density stance, theme mechanism, and the traps that have already cost a session.
Two apps can both meet the rubric and look nothing alike.

## Where a design doc lives

**Waypoint owns it for any onboarded service.** A design language is present-tense system
truth, so it belongs next to the service's other durable docs, not in a skill's private
folder:

```
~/Documents/obsidian/Engineering/<service>/design.md
```

It is a first-class Waypoint doc — `wp.py`'s `DEFAULT_DOCS`, mirrored by orient's
`WAYPOINT_DOC_KINDS`. That buys two things a local file cannot:

- **`wp stale` catches it.** Anchor `verified_paths` at the real token/component paths and
  the doc is flagged the moment the design system moves under it. An 86-day-old note
  claiming `--primary` was near-black is exactly what this prevents.
- **orient renders it** on `/plans` → Services, alongside the service's other docs with its
  staleness state.

Resolve one with `wp locate <repo>` (or `wp context <service>`), then read
`<vault>/design.md`.

| Doc | Covers |
| --- | --- |
| `Systems/ilg-platform/design.md` | **System-level root.** The ILG design system and the rules that outlive any one app. |
| `Engineering/ui-toolkit/design.md` | The detail: tokens, `G*` components, brand palette, radius. |
| `Engineering/fuse-ui/design.md` | Consumer: `--primary` overrides, `next-themes` wiring, reference module. |
| `Engineering/distraction-dashboard/design.md` | Consumer: inherits the toolkit with zero overrides. Not yet pixel-reviewed. |
| `Systems/fuse/design.md` | Fuse owns no language — points up to ilg-platform, names its surfaces. |
| `Systems/orient/design.md` + `Engineering/orient/design.md` | The opposite pole: dark-only, maximum density. |

**Start at the system, then read the service.** A system doc frames the stance; a service doc
carries the detail; a *consumer* service records only its **delta** from the parent. A
consumer that repeats the toolkit's tokens will drift from them.

## Calibration — the two poles

Same craft bar, opposite density, because the readers are opposite. Placing a surface here
before reviewing it is the fastest way to avoid importing the wrong house style:

```
                       built for its author
                                ▲
                                │   ● orient
                                │
        spacious ───────────────┼─────────────── dense
                                │
           ● fuse-ui            │
           ● distraction-dash   │
                                ▼
                    built for someone else
```

### The local fallback (this folder)

For a target with **no Waypoint folder** — `orient.md` today, plus any artifact or scratch
prototype. `orient` is not onboarded (it lives at `~/projects/orient`, outside `~/code`,
deliberately outside the Fuse org contract), so its doc stays here for now.

> Moving: `orient` is becoming a Waypoint **system**, at which point `orient.md` moves to
> the vault and this folder holds only genuinely un-onboarded targets.

**Always check the vault first.** A stale copy here shadowing a live vault doc is the worst
outcome.

## Adding a project

Onboarded service → write `<vault>/design.md`, then anchor it:

```
wp verify <service> design.md --paths <token/style/component paths>
```

Not onboarded → write `<name>.md` here, and note what it would take to onboard.

Fill every heading from **source and pixels, not memory**:

- **Identity** — what it is, who reads it, the density stance in one sentence.
- **Theme** — how light/dark is actually switched (this drives `capture.mjs`; get it wrong
  and every shot is the wrong theme).
- **Tokens** — real values, and where they are defined (often a *different repo*).
- **Type** — the scale as *measured* (`grep -rhoE "text-\[[0-9]+px\]" | sort | uniq -c`),
  not as imagined.
- **Components** — the idioms to reuse instead of reinventing.
- **Conventions** — the rules the codebase already keeps.
- **Traps** — what has already burned a session here.

Then add a row to the table above and to `SKILL.md`'s step 0.

## The rule this layer exists to enforce

**Never drag one project toward another.** The rubric's "density is a feature" warns against
bloating a dense tool into a marketing page — it is *not* a licence to compress a spacious
operator UI into a HUD. orient at fuse-ui's density would be broken; fuse-ui at orient's
density would be unusable by the support staff it is built for.

So: **load the project's design doc before the first screenshot.** Where a rubric judgement
and the design doc disagree about house style, the design doc wins. The rubric still wins on
what it owns — contrast, focus states, reflow, honest counts, designed states.

**Keep them current.** When a review finds a stated fact false, fix it in that session and
re-anchor with `wp verify`. A design doc nobody corrects is worse than none, because it is
trusted.
