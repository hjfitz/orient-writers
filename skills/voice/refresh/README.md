# Refreshing the voice guide

Re-mine when the terse or warm register numbers drift by more than about 10 points, when a new direct report
or close peer appears, or roughly each quarter. Full reasoning and limits: `~/Documents/obsidian/Voice/Method.md`.
**No corpus is kept here or in the vault** (private DMs, other people's context). Work in a scratch dir.

```bash
export VOICE_WORK=/tmp/voice-refresh && mkdir -p $VOICE_WORK && cd $VOICE_WORK
R=~/.claude/skills/voice/refresh
```

1. **Sample days.** Edit `PLAN` in `sample_days.py` for the window (weight recent months), then
   `python3 $R/sample_days.py <seed> 6` -> `manifest.json` (days per agent, round-robin).
2. **Collect.** One agent per manifest slice using `collector-prompt.md` (general-purpose agents, Slack
   search tool). Each writes `corpus-<n>.jsonl`. Spot-check 5 random rows against live Slack for exact text and ts.
3. **Filter and stats.** `python3 $R/analyse.py > analysis.out` also writes `human.json`. Check the
   machine-written share by month (it was rising: about 0% to 30% between Jun and Sep 2026) and that em or
   en dashes are still rare in the human rows. If not, tighten the filter before anything else.
4. **Cluster.** Edit the name sets in `cluster.py` for the current team, run it -> `cluster-<name>.jsonl`.
5. **Profile.** One agent per cluster with `profiler-brief.md` (each reads its whole slice, fetches context
   for about 30 replies, writes `profile-<name>.md` and a script).
6. **Verify, do not trust.** `python3 $R/verify_nums.py <name>` recomputes headline numbers;
   `python3 $R/verify_quotes.py <name>` checks quoted examples against the corpus. Expect descriptive phrases
   to show as unmatched. Fabricated quotes must be zero.
7. **Distil** into `~/Documents/obsidian/Voice/` (`Voice.md`, `Audiences.md`, `Registers/`). Diff the
   register tables against the old ones. Then `python3 $R/verify_vault.py` (quoted exemplars vs corpus).
8. **Validate** as in `Voice/Validation.md`: held-out days, guided vs control drafts, mechanical comparison,
   a blind pick from Harry. Give the drafters the substance. Keep the no-substance run as the control that shows
   what stalling looks like. Calibrate emoji and stock-phrase rates against the corpus, not one round.
9. Update `Method.md` and `Validation.md` with the new numbers, and delete the scratch dir.

The linter `../check.py` encodes the mechanical rules. If a rule changes in `Voice.md`, change it there too.
