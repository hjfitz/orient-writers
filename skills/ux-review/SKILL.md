---
name: ux-review
description: Review and lift a running front-end's UX to a fixed high bar — tool-grade craft (the Linear / Stripe / Raycast / Oxide lane, never decoration for its own sake), held at the density that app's readers actually need. Screenshots the real running app across viewport and theme, critiques every shot against rubric.md plus the project's own tracked design language in design/ (orient = dark-only monospace console; fuse-ui = light-first shadcn business UI on the ILG brand), emits a ranked backlog, then implements the fixes and re-shoots to prove the bar moved. Also the place the design language itself is recorded and kept current. Reusable across any project; owns the UX method only and defers landing the change to the target repo's own rules. Trigger when the user asks to review, improve or polish a UI or its UX, make a page look or feel better, asks what a project's design language or house style is, or runs "/ux-review [target]".
---

# UX review

Not a code review (`review-code` owns correctness) and not a one-off opinion. A repeatable
loop that drags a running front-end up to a fixed bar and proves it moved — with pixels,
not prose over JSX.

Two files, two jobs:

- `RUBRIC = ~/.claude/skills/ux-review/rubric.md` — the **universal bar**. House-style
  agnostic: the dimensions any UI is held against.
- `DESIGN` — **what this app actually is**: tokens, type scale, component idioms, density
  stance, theme mechanism, traps. **Waypoint owns it** for an onboarded service
  (`Engineering/<service>/design.md`, resolved with `wp locate <repo>`); the skill's own
  `design/` folder is the fallback for targets with no vault folder. Vault first, always.

Load **both** before the first screenshot. Where a rubric judgement and the design doc
disagree about house style, the design doc wins; the rubric still wins on what it owns —
contrast, focus states, reflow, honest counts, designed states. Both are meant to grow:
a durable craft lesson goes in the rubric, a fact about one app goes in its design doc.

**You must see the rendered pixels.** A UX judgement read off source is worthless at this
bar. Capture first, critique the images.

## The loop

**0. Target and design language.** A running URL and the routes to judge, plus the design
doc for that project:

| Project | Design doc | Theme | Default dev URL |
| --- | --- | --- | --- |
| fuse-ui | `Engineering/fuse-ui/design.md` | light default, `.dark` class | `code/Makefile` → `watch` |
| ui-toolkit | `Engineering/ui-toolkit/design.md` — **the detail** | same | `apps/showcase` |
| distraction-dashboard | `Engineering/distraction-dashboard/design.md` | check it | — |
| orient | `Engineering/orient/design.md` | dark only | `:3000`, persistent `next dev` |
| anything else | none yet — see `design/README.md` | establish it first | — |

Vault docs live under `~/Documents/obsidian/`; resolve with `wp locate <repo>`.

**Read the system before the service.** `Systems/<name>/design.md` frames the stance and says
who owns the language (`wp system list`); the service doc carries the detail, and a
*consumer* records only its delta — so for anything in the ILG suite, start at
`Systems/ilg-platform/design.md`. Check `wp stale <service>` before trusting a service doc:
they are anchored to the real token paths precisely so a moved design system shows as stale.

No design doc for the target? **Write one as step 0** (README has the headings) rather than
reviewing against another app's house style by reflex. That mistake is the whole reason this
layer exists: fuse-ui judged as if it were orient reads as "not dense enough", which is
wrong — it is a light, spacious operator tool for ILG support staff, by design.

If the app isn't up, start it — defer to the target repo's own `CLAUDE.md`/`agents.md`.
Grab **real** ids/routes and critique real content — never a hypothetical or an empty page
(empty is its own state to judge, but separately).

**1. Capture.**
```
node ~/.claude/skills/ux-review/capture.mjs <baseUrl> <route...> --out <scratchpad>/ux
```
Produces a PNG per route × {mobile, desktop} × {light, dark}. **Read every PNG** — the
critique is of the images, not the command output.

Shoot the viewports the **reader** uses, which the design doc states. Add
`--viewports mobile,desktop,ultrawide` (3440×1440, DPR 1) when the reader works on a wide
display; a layout that holds at 1440 can still be a wall of 3000px rows at 3440. For an
app with dark only, add `--themes dark`. A route with a tab or filter is a route per state:
pass `"/page?tab=x"` for each, since the tab that is empty in dev hides the one that isn't.

**2. Review.** Hold each shot against the RUBRIC, read through the DESIGN doc. Produce a
ranked backlog, most-egregious first. Every item names the **dimension**, the **exact
defect**, and a **valued fix** — "h2/h3 render at the same size; set a 1.25 scale, leading
1.3", never "improve typography". Value a fix in the project's **own** units: an orient fix
is `text-[11px]` and a token, a fuse-ui fix is `text-sm` and a `G*` component.
- **Stop here and show the backlog unless told to go straight through.** Review-only is a
  valid, complete outcome.

**3. Improve.** Take the top items (or the batch named). Implement respecting the target
repo's architecture rules, the rubric and the design doc's idioms — one coherent change at
a time, presentation only. Reuse the app's existing component before adding one. If a UX
fix would need a data/domain/meaning change, name it and stop: that's the user's call, not
a silent widening.

**When the design doc turns out to be wrong, fix it in this session** — and re-anchor a
vault doc afterwards (`wp verify <service> design.md --paths …`), or the next session
inherits a doc that reads current and isn't. Every one of these has already been stale once:
a token moved into a shared package, a `--primary` stopped being near-black. A
trusted-but-wrong design doc is worse than none.

**4. Re-shoot and prove.** Re-run capture on the touched routes. Put before/after side by
side and state which rubric dimension moved. If a shot didn't visibly improve, it isn't
done — say so rather than claiming it.

**5. Land it.** Defer **entirely** to the target repo — its `CLAUDE.md`/`agents.md` owns
build, test, lint, commit, PR, worktree and evidence rules. This skill never invents a
landing flow. (orient = direct-to-master plus its own operational lifecycle; fuse-ui =
worktree + PR + screenshot evidence.)

## Discipline

- **Density is set per project, not by taste.** Never "fix" a dense tool into a spacious
  marketing page — and never compress a spacious operator UI into a HUD. The design doc
  states the stance; follow it.
- **Both themes are first-class** wherever the app has two. Some apps deliberately have
  one (orient is dark-only) — say so explicitly rather than silently skipping the check.
- **The hard UX is in the edges** — dense-real-data, empty, loading, error — not the happy
  path. Shoot those deliberately.
- **Restraint beats ornament.** The eager reviewer's failure is adding flourish; the bar is
  signal.
- **Consolidating is where capability goes missing.** When a change retires a page, merges
  tabs or swaps a bespoke route for a generic one, `git show <sha>^:<file>` what the old one
  actually *rendered* before deleting it — the components, not the query. A retired page's
  purpose-built list (grouping, staleness, a fireable board) silently becomes a flat document
  list, and a commit message saying "the value is preserved" is a claim to check, not a fact.
  Then grep the old components for importers: zero means they are gone from the app.
- **A number the page prints is a claim too.** When two pages show the same figure, compare
  them in the same minute. When a lookup degrades to empty on failure, check nothing uses
  that empty result to decide *membership* — an outage then reads as a confident zero.

## Capture notes

- Uses the **system Chrome** via `puppeteer-core`, bootstrapped once into
  `~/.cache/ux-review` — never added to the target repo.
- Theme is applied **four ways at once**: `prefers-color-scheme` emulation, `localStorage`
  (seeded before page scripts), then `<html data-theme>` and the `.dark`/`.light` class
  after load. That covers media-query apps (orient) and class-strategy apps (fuse-ui via
  `next-themes`, which reads the stored key in its own blocking script) without a
  per-project patch. Override the key with `--theme-key <key>` if an app uses its own.
- **Still verify the shot is the theme you asked for.** A light page labelled `__dark` is
  the single most common way a theme review goes wrong — check the pixels, not the
  filename. An app that resists all four mechanisms needs a note in its design doc.
- The script hides Next's dev overlay (`nextjs-portal`): its "N" badge, its "1 Issue" pill, and
  — the one that bit — a **full-screen build-error modal for any route in the app**, so a
  sibling session's half-edited file elsewhere in the same dev server blanks every screenshot.
  If a shot is still wrong, `curl` the route: a 500 with the real content in the body is that
  same overlay, not your page.
- Only `localStorage` is seeded *before* page scripts; the attribute and class are set
  *after* load. Don't "improve" this by moving them earlier — writing to `<html>` ahead of
  hydration is itself a server/client mismatch, and React's dev overlay then stamps a
  **"1 Issue" badge into the screenshot**, which reads as an app bug that isn't one.
- `/today`-style routes that redirect or compile slowly may 000 on a cold first hit; warm
  the route with a `curl` once, then capture.
