# Collector agent prompt (one per slice of manifest.json)

You are collecting a raw corpus of Harry Fitzgerald's OWN Slack messages (Slack user id U0990E3P8BC) for a
writing-style analysis. READ-ONLY on Slack: never send, draft, react, or edit anything. Do not analyse or
summarise; faithful data collection only.

SETUP: load the Slack search tool (ToolSearch `select:mcp__slack__slack_search_public_and_private`).
Assigned days: <DAYS>. Output file: <WORK>/corpus-<N>.jsonl (append per day).

FOR EACH DAY: mcp__slack__slack_search_public_and_private with filters `from:<@U0990E3P8BC> on:YYYY-MM-DD`,
sort `timestamp`, sort_dir `asc`, include_context false, limit 20, natural_language_query "" (default channel
types). Follow the cursor until a page returns fewer than 20 results. Cap at 120 messages per day.

RECORD: one JSON object per line, keys exactly:
{"date","time","ch","kind":"dm|gdm|public|private","thread":bool,"ts","agent_suspect":bool,"suspect_reason","text"}
- ch: "#name", "DM:<other person>", or "GDM:<name1>+<name2>" (exclude Harry).
- thread: true if the permalink has thread_ts AND it differs from the message's own ts.
- text: VERBATIM, character for character, including typos, shortcodes and Slack markup. Escape newlines and quotes.
  Skip empty-text messages but count them.
- agent_suspect: true (with a reason) for messages that look machine-written: #real-agent-only or #agents-only,
  templated 'Deploying FUSE-... to dev', 'Reverted dev to master', 'PR for FUSE-...', PR-status digests, haude or
  human-sync voice, self-DM reports, long polished multi-paragraph or bulleted analysis, anything with em or
  en dashes. When in doubt mark true with the reason. Record them anyway.
- SECRETS (credentials, tokens, one-time-secret links, MFA codes): replace just that part with [REDACTED-SECRET].
Validate with python3 json.load per line. Report (under 150 words): rows per day, truncated or empty days,
empty-text skipped, agent_suspect count, tool problems.

Why the suspect flag matters: machine-written posts under his account rose from about 0% (Jan to Jun 2026) to
about 30% (Sep 2026) of his output. They carry em or en dashes 81% of the time, his own messages 0.05%.
