#!/usr/bin/env bash
# PreToolUse(Bash) gate: blocks git commit / git push / gh pr create when the diff
# adds a multi-line comment block to JS/TS source. Single-line comments are listed,
# not blocked. Exit 2 = block (stderr goes back to the model).
set -u
input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$cmd" ] || exit 0

mode=""
if printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])git([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+commit([[:space:]]|$)'; then mode=commit
elif printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])git([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+push([[:space:]]|$)'; then mode=push
elif printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])gh[[:space:]]+pr[[:space:]]+create([[:space:]]|$)'; then mode=push
fi
[ -n "$mode" ] || exit 0

repo=$(printf '%s' "$cmd" | grep -Eo 'git[[:space:]]+-C[[:space:]]+[^[:space:]]+' | head -1 | awk '{print $3}')
[ -n "$repo" ] || repo=$(printf '%s' "$cmd" | grep -Eo '(^|[;&|[:space:]])cd[[:space:]]+[^[:space:];&|]+' | head -1 | awk '{print $2}')
repo=${repo:-$cwd}
repo=${repo/#\~/$HOME}
[ -d "$repo" ] || exit 0
git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# orient is a personal tool, not a Fuse org repo (agents.md doesn't apply there);
# Harry's standing instruction (2026-09-18) is to skip this hook there entirely —
# commit-mode also diffs the full working tree, not just what's staged, so another
# session's unrelated unstaged WIP can otherwise block an unrelated clean commit.
toplevel=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null)
# Generated OpenAPI clients (`lib/gen/`) carry tool-emitted JSDoc, excluded from both diffs below.
[ "$toplevel" = "$HOME/projects/orient" ] && exit 0

if [ "$mode" = commit ]; then
  if printf '%s' "$cmd" | grep -q -- '--amend'; then base=HEAD~1; else base=HEAD; fi
  diff=$(git -C "$repo" diff "$base" -- '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.cjs' ':!**/lib/gen/**' 2>/dev/null)
else
  # Resolve the real default branch rather than guessing master-then-main: a
  # repo can carry a stale master (real default is main) or vice versa, and
  # diffing against the wrong one floods the report with old, unrelated
  # comments (reference_comment_density_hook_stale_master_base.md).
  def_ref=$(git -C "$repo" symbolic-ref -q refs/remotes/origin/HEAD 2>/dev/null)
  def_branch=${def_ref#refs/remotes/origin/}
  if [ -z "$def_branch" ] || [ "$def_branch" = "$def_ref" ]; then
    def_branch=""
    for b in main master; do
      if git -C "$repo" rev-parse --verify -q "origin/$b" >/dev/null 2>&1; then def_branch=$b; break; fi
    done
  fi
  [ -n "$def_branch" ] || exit 0
  base=$(git -C "$repo" merge-base HEAD "origin/$def_branch" 2>/dev/null || true)
  [ -n "$base" ] || exit 0
  diff=$(git -C "$repo" diff "$base"...HEAD -- '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.cjs' ':!**/lib/gen/**' 2>/dev/null)
fi
[ -n "$diff" ] || exit 0

report=$(printf '%s\n' "$diff" | awk '
  /^\+\+\+ / { file=substr($0,7); run=0; next }
  /^(---|@@|diff |index )/ { run=0; next }
  /^\+[[:space:]]*(\/\/|\/\*|\*)/ {
    line=$0; sub(/^\+/, "", line); gsub(/^[[:space:]]+/, "", line)
    run++; buf[run]=line
    if (run==1) singles[++ns]=file ": " line
    if (run==2) { blocks[++nb]=file ": " buf[1]; delete singles[ns]; ns-- }
    if (run>=2) blocks[nb]=blocks[nb] "\n    " line
    next
  }
  { run=0 }
  END {
    for (i=1;i<=nb;i++) print "BLOCK " blocks[i]
    for (i=1;i<=ns;i++) print "LINE " singles[i]
  }')

blocks=$(printf '%s\n' "$report" | grep -c '^BLOCK ' || true)
singles=$(printf '%s\n' "$report" | grep '^LINE ' | sed 's/^LINE /  /' || true)

if [ "$blocks" -gt 0 ]; then
  {
    echo "comment-density: $blocks multi-line comment block(s) added ($mode, base $base). House rule is no comment, or one line of non-obvious why. Collapse or delete before retrying:"
    printf '%s\n' "$report" | grep -A99 '^BLOCK ' | grep -v '^LINE ' | sed 's/^BLOCK /  - /'
    [ -n "$singles" ] && { echo "single-line comments also added (allowed, check each is needed):"; printf '%s\n' "$singles"; }
  } >&2
  exit 2
fi

if [ -n "$singles" ]; then
  ctx="comment-density ($mode): no blocks. Single-line comments added:\n$singles\nEach must say something the code cannot; delete any that restate it."
  jq -n --arg c "$(printf "$ctx")" '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$c}}'
fi
exit 0
