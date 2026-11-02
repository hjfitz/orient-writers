---
name: resolve-conflicts
description: Resolve the merge conflicts on a pull request branch by merging the base branch in, in a worktree, without pushing. Resolves mechanical conflicts (lockfiles, changelog order, imports, generated files) and any content conflict where both sides' intent is clear and the result keeps both; if even one file can't be resolved with confidence it aborts the merge and reports what a human has to decide. Runs headless (orient's "Resolve conflicts" button) or interactively. Trigger when the user asks to resolve, fix or clear the merge conflicts on a PR or branch.
---

# Resolve conflicts

Bring the PR branch up to date with its base by **merging** the base in, resolve the conflicts that can be resolved with confidence, and leave one local merge commit for a human to review and push. Nothing here ships anything.

This is stricter than `pr-clear` in one way and looser in another. `pr-clear` stops at any content conflict; this skill resolves one when both sides' intent is unambiguous, because its result is a local commit a human reads before it goes anywhere. It is never looser about guessing: **a conflict you can't explain is a conflict you leave.**

## Inputs

The prompt gives the PR (title, URL, head branch, base branch, head sha) and may carry a note from the user about what changed. You are in a git worktree at the PR head, on its own local branch. If you were started interactively with no worktree, create one per the org convention (`git worktree add -b <initials>/<desc> .claude/worktrees/<slug> origin/<headRef>`), never in a repo's main checkout.

## Rules

- **Merge, never rebase.** The PR branch may have commits others have seen; history is not rewritten.
- **Never push, never touch GitHub** (`git push`, `git remote`, `gh`, `curl` are denied in headless runs, and you must not look for a way round that). Never switch to or modify another branch.
- **Never stash.** The stash stack is shared across worktrees.
- **Don't change anything the merge didn't force.** No refactors, no formatting sweeps, no "while I'm here". A resolution is the smallest text that keeps both sides' intent.
- **Add no comments and no ticket references** to resolved code.

## Step 1 — Preflight

1. `git status --porcelain` must be empty and `git branch --show-current` must name a local branch. If not, stop and say so.
2. Note the starting commit: `git rev-parse HEAD`. Every abort path returns to it.
3. Preview what the merge will ask of you (it fetches `origin/<base>` itself; pass the bare branch name):
   ```
   node ~/code/.claude/skills/pr-clear/repair-helpers.mjs conflict-preview --base <base> --cwd . --format text
   ```
   It lists only the files that need a real decision. If it reports none, run `git merge --no-ff origin/<base>`. A clean merge commits itself, so go to Step 4 and skip Step 5.

## Step 2 — Merge and classify

`git merge --no-ff --no-commit origin/<base>`, then `git diff --name-only --diff-filter=U` for the conflicted files. Classify each:

| Class | Examples | Resolution |
| --- | --- | --- |
| **Generated** | lockfiles, snapshots, built output, OpenAPI/Go/TS codegen | Resolve the *source* files first, then **regenerate** — `pnpm install --lockfile-only` (pnpm 10; see the org note on mise's pnpm 9), the repo's own codegen script. Never hand-merge a generated file. |
| **Append-only** | changelog rows, route/export/barrel lists, enum members, registry entries | Keep both sides, in the file's existing order. |
| **Imports** | import blocks touched on both sides | Union of both, deduplicated, in the repo's ordering. Let the linter's fixer settle the order. |
| **Disjoint content** | both sides edited the same region but different statements; one side renamed or moved what the other edited | Apply both. For a rename-plus-edit, put the edit on the renamed code. |
| **Competing content** | both sides changed the same logic, condition, value, signature or test expectation in different ways; modify-vs-delete; one side's change depends on something the other removed | **Not yours to resolve.** |

For anything that isn't Generated or Append-only, establish intent **before** you edit:

- Their side: `git log --format='%h %an %s%n%b' HEAD..origin/<base> -- <file>` and the diff of those commits for that file.
- Our side: `git log --format='%h %s%n%b' origin/<base>..HEAD -- <file>` and the PR description from the prompt.

Resolve a file only if you can state in one sentence what each side was trying to do **and** the result does both. If you can't, it's Competing content, whatever it looks like.

## Step 3 — Stop condition

If **any** file is Competing content, or you couldn't establish intent for any file:

1. `git merge --abort`, then confirm `git rev-parse HEAD` equals the starting commit and the tree is clean.
2. Report (see below) with the unresolvable files, what each side did, and the exact decision needed. Also list the files you *would* have resolved and how, so the human doesn't redo that reasoning.

Do not commit a partial resolution and do not leave conflict markers anywhere. A half-merged tree is worse than none.

## Step 4 — Verify

1. No markers left: `git diff --check` and `git grep -nE '^(<<<<<<<|=======|>>>>>>>)( |$)'` over the tracked files you touched.
2. Install dependencies in the worktree if there is no `node_modules` (a worktree has none; don't link the main checkout's).
3. Run the repo's own gates for what you touched, as the repo defines them: tests, `lint` (use `lint:fix` where it exists), `build:check` and `build:check:tests` for a pnpm service. Run the narrowest set that covers the merged files first, then the full set.
4. If a gate fails, first decide whether the merge caused it: re-run the same failing command on `origin/<base>` in a throwaway worktree. A failure that reproduces there is **pre-existing**: don't fix it here, report it. A failure the merge caused (a renamed import, a signature that changed under the PR's call site) is yours to fix, minimally. If you can't fix it with confidence, treat it as a stop condition: `git reset --hard <starting commit>` and report.

## Step 5 — Commit

`git add` the resolved files by explicit path, never `-A`. Commit with the merge message:

```
Merge origin/<base> into <headRef>

Conflicts resolved:
- <path>: <one line: what each side did and what the result keeps>
```

End the message with whatever attribution line your instructions give. Do not push.

## Report

End with a short report the user can act on, in this order:

1. **Outcome** — merged and committed (`<sha>`), or aborted and why.
2. **Per file** — `path | class | how it was resolved | why that's safe`. For the ones where you used judgement, say what you'd want a human to check.
3. **Gates** — what you ran and the result; any pre-existing failure, named.
4. **To ship** — only if committed: the user pushes from the worktree themselves.
