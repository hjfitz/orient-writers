#!/usr/bin/env bash
# PostToolUse (Write|Edit): a Claude Code edit under the vault kicks the vault's git sync, so it
# reaches the other machines in seconds rather than on the next timer run. Never fails the tool call.
VAULT="${ORIENT_VAULT:-${WAYPOINT_VAULT:-$HOME/Documents/obsidian}}"
SYNC="$HOME/.local/bin/orient-vault-sync"
[ -x "$SYNC" ] && [ -d "$VAULT/.git" ] || exit 0
file=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
case "$file" in
  "$VAULT"/*) ORIENT_VAULT="$VAULT" "$SYNC" kick >/dev/null 2>&1 ;;
esac
exit 0
