# orient-writers

The tools that write orient's vault: Claude Code skills, `wp` (Waypoint), `cust` (Fuse Customers),
the statusline, and hooks. Claude Code reads them from `~/.claude`, which links here directory by
directory:

| `~/.claude` path | Links to |
| --- | --- |
| `skills/<name>/` (one link per skill) | `skills/<name>/` |
| `waypoint/` | `waypoint/` |
| `customers/` | `customers/` |
| `hooks/` | `hooks/` |
| `statusline/` | `statusline/` (`settings.json` runs `python3 ~/.claude/statusline/statusline.py`) |

`~/.local/bin/wp` and `~/.local/bin/cust` link to `~/.claude/waypoint/wp.py` and
`~/.claude/customers/cust.py`, so they resolve through these links unchanged.

## Rules

- **Link directories, never single files.** Claude Code's Edit and Write tools refuse to write
  through a symlinked file, but write through a symlinked directory normally.
- **`~/.claude/skills` itself stays a real directory.** Claude Code writes account-managed skills
  into `skills/synced/`, and two skills there are relative links into `~/.agents/skills`. Neither
  belongs here.
- **`.gitignore` is an allow-list.** `~/.claude` holds `.credentials.json`, session transcripts,
  `settings.local.json` (a prod key) and caches. Add a new top-level path to `.gitignore` on
  purpose; never widen it to everything.
- **Commits are scanned.** Run `git config core.hooksPath .githooks` once per clone. The pre-commit
  hook runs `gitleaks protect --staged` and refuses to commit without gitleaks installed.

## Adding a skill

Create it here under `skills/<name>/`, then link it:
`ln -s ~/projects/orient-writers/skills/<name> ~/.claude/skills/<name>`.
