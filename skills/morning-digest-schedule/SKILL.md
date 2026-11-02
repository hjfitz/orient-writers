---
name: morning-digest-schedule
description: "Arm, check or stop the weekday schedule that runs /morning-digest at about 08:00 and chains two cheap window-opener pings (about 05:00 and 10:05) so the 5-hour token windows refresh at about 10:00 and 15:05, inside an 08:30 to 16:30 day (Europe/London). Session-only: CronCreate jobs die with the session and auto-expire after 7 days, so this skill re-arms them. Trigger when the user asks to schedule, arm, re-arm, check or stop the morning digest schedule or the token-window pings, or says to start morning-digest-schedule."
---

# morning-digest-schedule — digest at 08:00, windows nested in the workday

This skill is only the **trigger layer**. The digest itself is the `morning-digest` skill; do not re-implement any of it here.

## The three jobs

Windows last 5 hours from the first prompt. The pings place the window boundaries mid-morning and mid-afternoon, where a refresh helps. A ping only matters for pulling a boundary earlier; a first prompt after a boundary opens a fresh window anyway, so there is deliberately no third ping.

| Cron (weekdays) | Prompt | Actual fire | Purpose |
|---|---|---|---|
| `28 4 * * 1-5` | `Window-opener ping for the token schedule. Reply with just: ok` | ~04:58 | opens the window that refreshes ~09:58 |
| `28 7 * * 1-5` | `/morning-digest` | ~07:58 | the digest, run fresh 3h after the opener |
| `35 9 * * 1-5` | `Window-opener ping for the token schedule. Reply with just: ok` | ~10:05 | opens the window that refreshes ~15:05 |

The digest stays at 07:58 and is not the opener. Run at 05:00 it would be 3.5h stale by 08:30.

## Why the cron minutes look early

`CronCreate` shifts each recurring job by a fixed offset of up to 30 minutes, and a daily job gets the full 30. The cron minutes above are already compensated. Always confirm against the **Next run** time in the `CronCreate` result, not the cron expression. The ~10:05 ping must land after the first window ends (~09:58); if it lands before, or any job lands more than 10 minutes from its table time, delete and recreate it with the minute adjusted.

## Arm

1. `CronList`. For each of the three rows, skip it if a job with that prompt and cron already exists, so re-arming never duplicates. Report the next run of any that exist.
2. Load the schema (`ToolSearch` `select:CronCreate,CronList,CronDelete`) and `CronCreate` each missing row with `recurring` true.
3. Tell the user, in four lines: the actual next-run time of each job, that all three are **session-only** (this Claude session has to stay open and idle, and the machine awake, at 04:58), that they **auto-expire after 7 days** so this skill is re-run weekly or after any restart, and that a suspended machine or closed session silently skips the chain.

## Rules

- **Window already open.** The first prompt of the day opens the window. If the session already got a prompt that day before 04:58, say so when arming, because the boundaries will not fall at 10:00 and 15:05.
- **No catch-up.** If the session starts after a job's fire time, do not run it on arming. Say the next run is tomorrow, and run `/morning-digest` now only if the user asks.
- **Ping replies.** A ping gets the one-word reply `ok` and no tool calls, so it costs almost nothing. Never treat it as a request to do other work.
- **Weekends and holidays.** The crons skip Saturday and Sunday. They do not know bank holidays; the user deletes the jobs or ignores the runs.
- **Weekly cap.** This assumes the 5-hour window is the binding limit. More windows do not help if a weekly cap is.

## Stop

`CronList`, then `CronDelete` every job whose prompt is `/morning-digest` or starts with `Window-opener ping`. Say all three are cancelled.
