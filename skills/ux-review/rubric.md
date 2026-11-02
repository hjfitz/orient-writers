# The bar

North star: **tool-grade craft.** Every pixel earns its place by carrying information or
affordance; nothing is there to perform. This file is the **universal** bar — it is
deliberately house-style agnostic.

**House style is not here.** How dense, how dark, how rounded, which components — that is
the project's own design doc under `design/`, and it wins over any instinct this file gives
you. The two live questions it answers are *how much density is right for this app's
reader* and *what does this app already look like*. Judging every app against one house
style is the failure this split exists to prevent.

## Anchors

These calibrate **craft**, not house style. Read them as "made to this standard", never as
"should look like this".

- **The project's own design doc** — the real calibration reference. If a change would make
  the app feel less like itself, it's wrong, whichever anchor below it moves toward.
- **Linear** — density with restraint; motion that clarifies rather than decorates.
- **Stripe** — typographic discipline and unambiguous hierarchy.
- **Raycast** — keyboard-first, dense, crafted; a tool that respects an expert user.
- **Oxide Computer** — engineering-console confidence: a monospace-led type system, a
  near-black palette lit by one or two functional accent colours, schematic diagrams used
  as real information rather than illustration, and a grid held with total discipline.
  Restraint read as authority, not minimalism for its own sake.
- **Modern Warfare / tactical-HUD** — operator instrumentation, taken for its *hierarchy*,
  not its chrome: sharp unrounded corners, dense tabular/monospace readouts, one alert
  colour spent only on what actually needs it, confident asymmetric layout that still
  reads instantly under pressure. This is the highest-risk anchor to misread — see the
  anti-pattern below before reaching for it.
- **Anti-pattern — decoration outrunning function (the "Vercel" failure):** generally
  clean, but flourish for its own sake — gratuitous gradients, glows, oversized hero
  whitespace, motion that only performs. When craft becomes ornament, it fails this bar.
  The test: remove the effect — is any information or affordance lost? If not, it's noise.
  A HUD corner-bracket or scan-line with no data behind it is this same failure in
  fatigues — the tactical anchor above lends its *discipline*, never its cosplay.

The lane is the product-tool lane, never the agency-showreel lane.

**Density is a feature — at the level the app's reader needs.** The Oxide and HUD anchors
suit a console built for the engineer who wrote it (orient). They are the wrong target for
an operator tool used under pressure by staff who did not build it (fuse-ui), where
scannability and generous hit areas *are* the craft. Take the density stance from the design
doc, then hold the app to every dimension below at that density. "Not dense enough" is only
a finding when the design doc says so.

## Dimensions

Hold every screenshot against these. Each has a *good* and a *failing tell*.

1. **Typography.** A real scale with visible steps between levels; consistent leading
   (~1.3–1.5 body, tighter for headings); a sane measure (~45–80ch); weight/color for
   hierarchy over size alone. *Fail:* h2 and h3 the same size; walls of one weight;
   line-height that makes dense lists shimmer.

2. **Spacing & layout.** One spacing scale used everywhere; a real alignment grid; optical
   balance; padding that scales with density, not a single hard-coded value. *Fail:*
   near-but-not-equal gaps; content hugging one edge; arbitrary margins per component.

3. **Color & contrast.** Token discipline (no raw hex in components — though an app whose
   token set has no `success`/`warning` may have a documented literal-scale convention for
   status tints; the design doc says which); **every theme the app ships is first-class and
   at parity**; AA minimum on text; restraint — a small palette, color used to mean
   something. *Fail:* a fix that only holds in one theme; low-contrast greys; color as
   decoration with no semantic.

   A single-theme app is a legitimate design decision, not a gap — discharge the check
   explicitly ("dark-only by design, light shots identical") rather than skipping it, and
   never add a second theme as a review finding.

4. **Hierarchy & signal.** One clear focal point per view; the eye lands where the value
   is; progressive disclosure for depth (collapse the rare, surface the frequent). *Fail:*
   everything shouts equally; the most important number buried; no scannable structure.

5. **Motion.** Purposeful and fast (~120–240ms), eases naturally, respects
   `prefers-reduced-motion`; used to explain a state change. *Fail:* jank, layout shift,
   motion that only performs, animation on every element.

6. **Component consistency.** Shared idioms across views — a card, a row, a chip, a link
   look and behave the same everywhere. *Fail:* one-off styling per page; three button
   shapes; the same concept rendered differently on two routes.

7. **States.** Empty, loading, error and **dense-real-data** are all designed — the hardest
   UX is not the happy path. Skeletons over spinners; empty states that teach; errors that
   say what to do. *Fail:* an empty page that looks broken; a spinner where a skeleton
   belongs; a layout that only holds with three rows and collapses at thirty.

   **Count the rows against the source.** A list that caps, filters or clamps and then
   renders `count={rows.length}` asserts a total it isn't showing — the page lies and looks
   fine doing it. Check every limit on the path (page slice, domain default, *and* any
   shared query clamp — they stack silently), and any `.filter()` that can drop a record on
   a parse miss rather than rendering it as incomplete. This is invisible in a screenshot;
   query the data and compare.

8. **Responsive.** Works at real phone width (~390px) with no horizontal scroll; a 16px
   gutter; reflow, not shrink-to-fit. *Fail:* a fixed desktop layout squeezed; tap targets
   under ~40px; a table that overflows the viewport.

   **"No page scroll" is not the whole check.** A `table-fixed` table can fit the viewport
   while its cells spill into their neighbours — a chip or a nowrap label wider than its
   column overruns the next one. Measure it: count `td`/`th` whose `scrollWidth` exceeds
   `clientWidth`, per page, at 390px. To drop a column on a phone, hide the `<col>` as well as
   its cells — under `table-fixed` a hidden cell's `<col>` keeps reserving its width (measured:
   252 of 360px used, versus 360 with the `<col>` hidden too). A chip wider than any phone
   column can't be fixed by sizing; move it under the row's title instead.

   **Wide is a viewport too.** When the design doc says the reader works on an ultrawide,
   shoot `--viewports ultrawide` (3440×1440) as well. The failure there is a row that spans
   the screen: a label and its value a thousand pixels apart, so the eye cannot track across
   it, and a single column of them that is mostly empty space. The fix is columns, not
   stretch and not a narrow column centred in the void: a two-pane page grid (live state
   beside its history) once the viewport can give each pane the width its widest table needs,
   or a long flat list grouped by a key and flowed with CSS `columns` so it fills the width.
   Check the pane breakpoint against the widest table in it (a 950px table in a 670px pane
   scrolls sideways, which is worse than one column).

9. **Craft micro-details.** Visible focus rings; hover and cursor affordances on everything
   interactive; consistent corner radii, shadows, borders, icon alignment and optical
   sizing. This tier is what separates "fine" from award-grade. *Fail:* no focus state;
   misaligned icons; a 1px seam; a shadow that doesn't match its neighbours; a state label
   rendered in the same box as the button beside it, so a finished row invites a click.

   Two that look done in source and aren't — always re-shoot scrolled: an `overflow-x`
   ancestor becomes the scroll container a `sticky top-0` header anchors to, which kills it
   silently (drop the wrapper and size columns proportionally instead); and emoji used as
   status glyphs come from a different font with their own advance width and baseline, so
   they break a monospace grid and carry no word — draw swatches from colour tokens and
   give them a legend.

10. **Perceived performance.** Feels instant; content paints progressively; nothing blocks
    on the slowest thing. *Fail:* a blank hold then a full paint; layout that jumps as data
    arrives.

## Verdict

- A backlog item is valid only when you can name the **dimension**, the **exact defect**,
  and a **valued fix** (numbers, not adjectives — "1.25 scale, leading 1.3", not "nicer
  type").
- A route only meets the bar when it holds in **both themes at both viewports**.
- When in doubt, favour the anchors' restraint. The failure mode of an eager reviewer is
  adding ornament; the bar is signal.
