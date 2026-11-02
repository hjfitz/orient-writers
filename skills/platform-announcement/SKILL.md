---
name: platform-announcement
description: "Draft a Platform Engineering launch announcement, a geekier sibling of Jack's Fuse product announcements in #bifrost-announcements. Produces the same pair: a short Slack post for #ilg-platform (📣 headline, ✅/⚠️ list, shoutout, link) and a Confluence blog post in the PLTE space. It's written for engineers on other teams: what the mechanism is, the contract and its version line, the adoption diff, how it was proven and where the sharp edges are. Researches the capability from PRs, tags, consumer code search and the vault, verifies every version, digest and count, then saves the long form as a Confluence draft preview and the Slack post as a draft in Harry's composer. Harry attaches any visual and sends it himself. Trigger when Harry asks for a platform announcement, to announce a platform capability (a golden image, a reusable workflow release, a terraform module, shared DNS, a shared package), or runs /platform-announcement <thing>."
---

# Platform announcement

One capability, one announcement. This is the **Platform Engineering counterpart to Jack's
`#bifrost-announcements` posts**: same shape and the same pair of artefacts, written for a
different reader.

| | Jack's Fuse announcement | This skill |
| --- | --- | --- |
| Reader | ILG support, L2, projects, ops | Engineers on every team: Fuse, SRE, Tech Services, Merak |
| Question it answers | "What can my customer do now?" | "What do I change in my repo, what am I signing up to, and what breaks?" |
| Headline | `:mega: *New in Fuse: <title>* :tada:` | `:mega: *New in Platform: <title>* :tada:` |
| Visual | A wide GIF of the UI | The adoption diff as a code block. Add a terminal GIF if there is one |
| Long form | Bifrost space blog, `Fuse Product Announcement: <title>` | PLTE space blog, `Platform Announcement: <title>` |
| Body vocabulary | No identifiers | `uses:` lines, `FROM` lines, module sources, tag lines, digests and package versions are the content |

"Geekier" means **the mechanism and the contract**, not more words. The Slack post stays as short as
Jack's. The depth goes in the blog.

Harry's own `#ilg-platform` post on shared DNS (2026-09-16) is the closest existing example of the
register: what changed, the convention, "Using it" with the real state bucket, prefix and role names,
who owns what, and where to ask. Read it before drafting:
`slack_read_channel C0B95TS1XTM`, Harry's message starting ":globe_with_meridians: **Shared engineering DNS is ready!**".

---

## Configuration

```
SLACK_CHANNEL   = #ilg-platform (C0B95TS1XTM)        # cross-team platform channel. Confirm per run (below)
JACK_CHANNEL    = #bifrost-announcements (C0C6MP9TSER) # style reference only. Never post or draft here
CONFLUENCE      = cloudId 506e1245-70c1-48d9-aa91-8ae1b7da6eff, space PLTE (id 246611972), contentType blog
JIRA_PROJECT    = PLTE                                # sparse. Most platform work is PR-only
PLATFORM_ORGS   = ilg-platform (github-actions, images, terraform-modules, core-infra, gcp-config,
                  observability-sdk, ui-toolkit, platform-mcp-server, repo-template)
                  gfs-bifrost (pkg-node packages, .github)
CONSUMER_ORGS   = gfs-bifrost, ilg-platform, ilg-tech-services, gfs-sre, ilg-merak
ARCHIVE_DIR     = ~/Documents/obsidian/Digests/Platform/
SLACK_MAX       = ~1500 chars                         # Jack's posts run 900–1400. Over that, move it to the blog
```

## Step 0 — Pin the subject

The argument names **one** capability: `/platform-announcement golden images`,
`/platform-announcement github-actions 0.2-bonbon`, `/platform-announcement shared DNS`.

- No argument: list the candidates from the last ~3 weeks (merged PRs in `PLATFORM_ORGS` that
  publish something: a tag move, an image, a package version, a module release, a new shared
  resource), and recommend the one most worth announcing. Ask a single yes/no.
- Several things in one go is a roundup, not an announcement. Pick the headline capability and fold
  the rest into "What's next" or leave them out. Jack never bundles.

## Step 1 — Is it actually announceable?

A platform announcement asks other teams to adopt something, so it has a higher bar than a Fuse one.
**Stop and tell Harry** rather than drafting if:

- **It isn't on its stable line yet.** For example, only a `:1`-style or pre-release tag exists, the
  rolling tag hasn't been cut, or the package isn't published.
- **Nothing outside the platform team has run it.** One real consumer canary is the minimum. If the
  only consumer is the repo's own CI, it's not ready.
- **A known open follow-up blocks a typical consumer.** One example: the cloud-run module still
  hard-codes a sidecar the new image makes redundant. Name it, and either it goes in ⚠️ or the
  announcement waits. Harry decides which.

## Step 2 — Gather (verify everything, don't recall it)

Every version, digest, tag, count, path and role name in the post is a claim a reader will paste
into their repo. **Each one gets checked against the live source in this run**, not copied from a
memory, a plan or an earlier turn. That's the user-level decisiveness rule applied to prose.

**A. What shipped.** Merged PRs for the capability:
```bash
gh search prs --owner ilg-platform --owner gfs-bifrost --merged --merged-at '>=<date>' \
  --json number,title,repository,author,closedAt,url --limit 100 -- "<keywords>"
```
Read the PR bodies, not just the titles: the design decisions and the rejected alternatives live
there. Record the authors for the shoutout. Don't use `mergedAt`. That field doesn't exist, so use
`closedAt`.

**B. The contract and its version line.** Pin the published coordinates exactly:
- Reusable workflow → the tag line (`0.1-affogato`, `0.2-bonbon`; the sweet-things naming is
  alphabetical, see the PLTE Confluence "Rolling Tag Versioning & Releases" page 249593955), whether
  this was a **force-move** (backward-compatible) or a **new line** (breaking), and the exact
  `uses:` line.
- Image → registry path, rolling tag, immutable `-<sha7>` tag and today's **digest**
  (`gcloud artifacts docker tags list <registry>/<image>`). Consumers build `FROM :<line>` with
  **no digest** (images#9 reversed the earlier digest-pin guidance), so the adoption diff uses the
  bare rolling tag. The digest goes in the blog's contract section as "today's value".
- Package → published version from the registry (`pnpm view <pkg> version`) and its Package
  Changelog entry in `~/code/CLAUDE.md`.
- Terraform module → `source` + `ref`, and the remote-state bucket/prefix and outputs it exposes.
- Shared resource (DNS, WIF, registry) → the IAM role, the bucket/prefix and the allowlisted orgs.

Say explicitly whether it's **additive** or **breaking** (see `platform-hat`). A breaking change
gets a migration section in the blog and a ⚠️ line in Slack, without exception.

**C. Who it's for: consumers, by search.** Never from memory:
```bash
gh search code --owner <org> '<the uses:/FROM/source string>' --json repository,path
```
Run it once per org in `CONSUMER_ORGS`. Code search allows **10 calls a minute**, so a
five-org fan-out across several queries hits a 403 rate limit. Run the batch in the background
with `sleep 7` between calls, and wait on it with Monitor. Check `gh repo view --json primaryLanguage`
on each hit before counting it as eligible, and drop templates and IaC-only repos. Code search is
also SAML-blind for some orgs (see
[[gh-search-saml-blind]]). If a search returns nothing for an org you know has repos,
say "couldn't search <org>" instead of "no consumers". Produce two numbers: **already on it** and
**eligible to move**. "Eligible" means repos carrying the thing it replaces, for example a hand-rolled
`serverless-init` sidecar, a per-repo `apk upgrade libssl3` or a pre-rename workflow filename.

**D. How it was proven.** The canary repo and revision, the deploy run, contract tests, and the
before/after a consumer would actually notice (log `source` tag, image size, CVE count, cold start,
build minutes). Measured values only. If a number wasn't measured, it isn't in the post. In
Datadog, Fuse's prod/dev split is the `@environment` **attribute**; `env` is `serverless` on
everything, and a bare `environment:prod` tag query returns nothing.

**E. The sharp edges.** From PR review threads, the vault and memory: what a consumer has to restate
or watch for. Examples: `USER nonroot:nonroot` because Semgrep can't see the base image's USER, a
minimum package version a service needs first, glibc vs musl. These are the most valuable lines in
the announcement. Engineers trust a post that tells them where it'll bite.

**F. Context sources.** Read these before re-deriving anything:
- Waypoint: `wp locate <repo>`, then the repo's explainers and plans.
- Memory: the `project_*` file for the programme, e.g. [[project-golden-images]] or
  [[ilg-platform-dns-migration]].
- PLTE Confluence docs tree ("3. Reusable CI/CD" and siblings) to find the reference page to link.

## Step 3 — Compose the pair

### Slack post (Jack's skeleton, platform payload)

```
:mega: *New in Platform: <title in plain words>* :tada:

<2–3 sentences. The problem every team has today, in concrete fleet terms
("~20 repos hand-roll a Datadog sidecar"), then what the platform now provides instead.>

:white_check_mark: <what you get: the capability, stated as a fact>
:white_check_mark: <the contract: tag line / digest-pinned / additive, and who's already on it>
:white_check_mark: <proof: the canary and what it showed>
:point_right: <who it's for / who should move first / what it doesn't replace>
:warning: <the sharp edge a consumer will hit>
:soon: <the next step, if one is genuinely scheduled>

```<the adoption diff: the one to three lines a consumer actually changes>```

Big shoutout to <@U…> for <the concrete outcome they delivered> :raised_hands:

<one-line call to action> :point_down:
:link: <blog url|Platform Announcement: <title>>
```

Rules:
- **Same emoji grammar as Jack's.** ✅ is what you get, ⚠️ is a gotcha, 👉 is guidance, 🔜 is next.
  No new section headings in the Slack post.
- **The diff block is the visual.** Keep it to what a consumer pastes, e.g.
  `FROM europe-west2-docker.pkg.dev/ilg-platform-ec02/images/go-runtime:0.1-affogato`. If Harry
  has a terminal GIF or screenshot, he attaches it when sending; the draft tool can't.
- **Identifiers are allowed, ticket keys aren't.** Repo names, tags, images and packages belong
  here. PLTE/FUSE keys don't: they mean nothing to the other teams.
- **Shoutouts are outcome-led and come from the PR authors in 2A,** with mentions resolved by
  email (see [[mcp-slack-markdown-format]]). Never credit Claude. If Harry built it alone, the
  shoutout goes to whoever canaried, reviewed or tested it. If there's nobody, drop the line rather
  than inventing one.
- **Format for the Slack MCP:** standard markdown, `**bold**`, `[label](url)`, `- ` bullets, no
  tables, `<@U…>` mentions passed through as-is.

### Confluence blog (Jack's skeleton, deeper sections)

Title: `Platform Announcement: <title>, <the hook>` (Jack's form, e.g. "Dictionaries, one table
instead of a wall of rules").

```
[NEW] [<AREA: CI/CD | IMAGES | TERRAFORM | NETWORKING | PACKAGES>] [PRODUCTION] [BREAKING, only if so]

**TL;DR:** <three sentences: what it is, who should care, what they change.>

<The problem today, in fleet terms, with counts from 2C.>

> <the one-line hook, like "New code? Add a row, not a rule.">

| | Before | Now [new] |   ← 4–6 rows. Concrete: patch latency, where config lives, who owns what

## 🔧 How it works
The mechanism, one level below what a consumer needs: what's baked in, what the entrypoint does,
how the tag moves, what the module creates. A diagram if a picture earns it.

## 📦 The contract
What is API surface (lockstep-stable) and what's free to change. The version line and its rule
(force-move = compatible, new line = breaking). How to pin. What's out of scope.

## 🚚 Adopting it
Numbered steps, each a real diff, taken from the canary PR (the canary PR is the recipe).
Link it as a worked example. Per-language or per-runtime subsections if they differ.

## 🧪 How we know it works
Canary repo + revision, the contract test, the before/after measured in 2D.

## 🪤 Gotchas
The 2E list, one bullet each: the symptom, then the fix.

## 🤝 What changes for existing services?
Usually **Nothing until you opt in.** Say so explicitly, the way Jack does. If something
does change without opting in, that's the first line of the TL;DR, not buried here.

## 🔭 What's next
Only scheduled or in-flight follow-ups. Each gets one line.

---
_Questions, bugs or a repo that needs access? Shout in #ilg-platform. Reference: <PLTE docs page>.
Receipts: <PR links>._
```

Use HTML (`getContentFormatGuide` first) for the status lozenges and table. **Send raw, unescaped
HTML**, then verify the write with an `adf` read. See [[feedback_confluence_html_must_be_unescaped]];
a markdown or html read-back proves nothing.

### Voice

Harry's, in the `channels` register (`~/Documents/obsidian/Voice/Registers/channels.md`), warmer than
his terse replies, as in the DNS post. A few rules carry most of the weight:
- Take positions ("this is the default for new services"), not hedges ("you may wish to consider").
- No filler closers ("let me know if you have any questions"). End on the specific ask, like the DNS
  post's "reply in this thread".
- British spelling.

## Step 4 — Review, draft, archive

1. **Print both drafts in the terminal.** Under them, list each verified claim and its source in one
   line apiece, plus anything you **withheld** and why (unmeasured, unverifiable, an org you couldn't
   search). Iterate until Harry approves.
2. **Confirm the channel** in one line: "drafting to #ilg-platform, ok?" A skill's configured
   default is not confirmation; see [[slack-channel-routing]]. If Harry wants a cross-post,
   e.g. to `#bifrost-general` for Fuse engineers, that's a second draft he asks for.
3. **The long form is a PLTE *page*, not a blog post.** PLTE rejects every blog create through the
   MCP, draft or current (`400 Could not create content with type blogpost`). Blog creation works in
   Bifrost, so the block is a PLTE space setting or a missing add-blog permission, not the tool
   (verified 2026-10-28). Harry chose a page over waiting for the permission.
   - Create the page with `status: draft`, titled `[DRAFT preview] Platform Announcement: …`, as an
     empty probe.
   - Write the full body with `updateConfluencePage` (`status: draft`) and verify it with an `adf` read.
   - Link its tiny URL (`/wiki/x/…`) in the Slack draft for review.
   - **On Harry's approval**, publish that same page: `updateConfluencePage` with `status: current`
     and the real title, dropping `[DRAFT preview]`. Publishing is outward-facing, so get an explicit yes.
   - The tiny URL survives publishing, so the Slack text needs no swap.
   - If PLTE ever allows blogs, switch back to `contentType: blog`. Test it with a draft probe first.
     The MCP has no delete, so a probe needs deleting by hand.
4. **Create the Slack draft** with `slack_send_message_draft` in `SLACK_CHANNEL`. It lands in Harry's
   composer: no "Sent using Claude" footer, he can attach the visual, and he presses send. Use
   `slack_send_message` only if Harry explicitly says to post it for him, and then expect the footer.
   If the call returns `attached_draft_exists`, tell Harry; don't overwrite it.
5. **Archive** to `ARCHIVE_DIR/<YYYY-MM-DD>-<slug>.md`, with frontmatter
   `tags: [platform-announcement]`, `channel`, `confluence_url`, and the final Slack text, the claim
   list and the withheld notes.

---

## Gotchas

- **Never post or draft in `#bifrost-announcements`.** Jack owns it and posting there is
  restricted. It is read-only for this skill, as the style reference.
- **Don't impersonate Jack.** Borrow the structure and emoji grammar, never his byline, his
  sign-offs or the "Fuse Product Announcement" title. These are Harry's posts, from Platform.
- **Code search undercounts silently.** An empty result across an org is "couldn't see" until
  proven otherwise. Cross-check one repo you know consumes it.
- **Rolling tags move.** Quote the digest you verified *today*, and say in the blog that the
  rolling tag is the contract and the digest will change.
- **Memory and plans go stale within hours on fast-moving programmes.** On the first run, the
  memory had a node24 digest and a "pin the digest" rule that had both been superseded the same
  day. Read the repo's README and its latest merged PRs before trusting either.
- **The PLTE Jira board is sparse.** Most platform work never gets a ticket (release steps
  deliberately don't, see [[open-pr-is-in-development]]). Don't treat a missing ticket as
  "not done": PRs and tags are the record.
- **One announcement per capability.** If the draft needs a second ✅ list, it's two announcements,
  or one of them belongs in 🔭.
