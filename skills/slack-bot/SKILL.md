---
name: slack-bot
description: Send an explicitly requested Slack message, threaded reply, or reaction through Bifrost Support Bot. Use for direct Slack delivery from Claude Code when Slack MCP is unavailable, and for any automated reply the support-triage/support-watch skills post under the bot's identity rather than the human's.
---

# Bifrost Support Bot

Use the installed production Slack app rather than Slack MCP. The CLI reads the bot credential from the local Slack CLI store; never copy, print, or ask for its token.

Run commands from `~/code/fuse/bifrost-support-bot` using:

```sh
~/.slack/bin/slack
```

Production app and workspace:

- App ID: `A0C2EJ3FMFD`
- Team ID: `T0561688FEJ` (GFS Engineering)

## Sending

Only send when the user explicitly asks to send the message — or, for `support-triage`/`support-watch`, when their own sign-off/autonomy rules say the reply is ready to post. First validate access with the read-only command:

```sh
slack api auth.test --app A0C2EJ3FMFD --team T0561688FEJ
```

For a DM, resolve or resume the conversation with `conversations.open users=<Slack-user-ID>`, then post with `chat.postMessage` to the returned channel ID. The bot has `chat:write`, `im:write`, `reactions:write` and `pins:write`; do not broaden its scopes further without the user's request.

Scopes live in `bifrost-support-bot/manifest.json` (manifest source is local). After editing it, push and reinstall with `slack install --app A0C2EJ3FMFD --team T0561688FEJ` from that directory. Don't also pass `--environment`, because the CLI rejects it alongside `--app`.

Use a JSON body for the message. Check every Slack response's `ok` field and report errors plainly. Do not use the old local app `A0C3F499WHW`.

## Replying in a thread

Post directly to the channel ID with `chat.postMessage`, passing the parent message's `ts` as `thread_ts` (the same channel/ts pair `mcp__slack`'s read tools already returned when the thread was read) — no separate lookup needed:

```sh
slack api chat.postMessage --json '{"channel":"<channel-id>","thread_ts":"<parent-ts>","text":"<reply>"}' --app A0C2EJ3FMFD --team T0561688FEJ
```

**A plain threaded reply is invisible on the channel's main timeline** — Slack only shows it to someone who opens the thread. When the calling skill's own instructions say the reply should also surface in the channel (e.g. `datadog-triage`'s Step 5 verdict, posted to a channel of on-call engineers scanning the feed, not just the one alert thread), add `"reply_broadcast":true` to the same call:

```sh
slack api chat.postMessage --json '{"channel":"<channel-id>","thread_ts":"<parent-ts>","reply_broadcast":true,"text":"<reply>"}' --app A0C2EJ3FMFD --team T0561688FEJ
```

Default to a plain threaded reply (no broadcast) unless the calling skill asks for broadcast — a broadcast copy in the channel for every reply on a long back-and-forth thread (e.g. a `support-triage` escalation) is noise, not signal.

## Reacting

```sh
slack api reactions.add --json '{"channel":"<channel-id>","timestamp":"<message-ts>","name":"<emoji-name>"}' --app A0C2EJ3FMFD --team T0561688FEJ
```

## Pinning

```sh
slack api pins.add --json '{"channel":"<channel-id>","timestamp":"<message-ts>"}' --app A0C2EJ3FMFD --team T0561688FEJ
slack api pins.remove --json '{"channel":"<channel-id>","timestamp":"<message-ts>"}' --app A0C2EJ3FMFD --team T0561688FEJ
```

The bot has no `pins:read`, so it can't list a channel's pins. A caller that needs to unpin later
must record the `ts` it pinned (`snap-maintenance` keeps a state file).

## Division of labor with `mcp__slack`

The bot's scopes are write-only (post, DM, react, pin) — it cannot read. `support-triage`/`support-watch` keep using `mcp__slack` (your own identity) for everything read-side: `slack_read_thread`, `slack_read_file`, resolving channel/user IDs. Only the reply itself — the thread post, the DM, the ack reaction — goes out as Bifrost Support Bot, so a colleague reading the channel can tell at a glance which replies were automated.
