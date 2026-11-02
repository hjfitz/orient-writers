---
name: voice
description: Draft a Slack reply (DM, group DM, channel or thread) in Harry's own voice, from the evidence-backed style guide in the Obsidian vault. Asks for the point Harry wants to make first, reads the conversation, picks the register for the reader, drafts as a short burst, lints it against the hard rules, and shows it in chat without sending. Trigger when Harry asks to draft, write or reply to a Slack message "in my voice" or "as me", pastes a Slack permalink and asks for a reply, or runs /voice. Not for haude or agent-to-agent rooms (use the haude skill), and not for email, PR comments or Jira.
---

# voice

Draft a Slack reply that sounds like Harry. The guide is `~/Documents/obsidian/Voice/` (built and validated
2026-09-30, see `Voice/Validation.md`). This skill is a thin workflow on top of it. **Draft only. Never send.**

```
GUIDE     = ~/Documents/obsidian/Voice
CORE      = $GUIDE/Voice.md              # hard rules, register selector, emoji budget, substance first
AUDIENCES = $GUIDE/Audiences.md          # person -> register, per-person overrides
REGISTERS = $GUIDE/Registers/{peers-terse,up,reports,wider,channels}.md
LINT      = ~/.claude/skills/voice/check.py
```

## Why the workflow is shaped this way

Blind tests showed the giveaway was never punctuation or case. It was **substance**: his real replies take a
position, give a fact or a guess, own a mistake, or ask a specific question back. A drafter left to fill the
gap writes "I'll look in to it" and "shout if you need anything", which he writes in under 1 message in 100.
With the point supplied, drafts passed as his at chance level (6 of 15 identified). So the skill supplies the
**wording** and he supplies the **point**.

## Steps

### 0. Get the point

Harry's request should say what he wants to say, even loosely: "tell Jack yes but not before Thursday", "say it
was my bad". If it does not, and the thread does not make it obvious, ask **one line**: "what's the point:
yes, no, a guess, a fact, or a question back?". Do not draft a stalling reply ("I'll check and come back") in
its place unless that genuinely is what he wants to say.

Stop and ask instead of drafting when the reply is about: health, family, money, hiring, performance or
corrective feedback about a named person, credentials, or anything that commits him to a date or promise he
has not stated. His own pattern for corrective feedback is to move it to a 1:1 or a coffee. Say so.

### 1. Rehydrate

Read `CORE` and `AUDIENCES`. Then read the register file for this reader (table in `CORE`). Do this every
time, not from memory: the guide is corrected as drift shows up.

### 2. Read the conversation

Never draft from the request alone. Fetch what he is replying to and his own recent messages in it:

- Given a permalink: `slack_read_thread` (thread reply) or `slack_read_channel` with `oldest`/`latest` around
  the `ts`.
- "Reply to Jack" or a person: `slack_read_channel` with their user id as `channel_id` (`slack_search_users`
  to find it), last ~15 messages.
- "Reply in #channel": `slack_read_channel`, last ~15 messages, and the thread if there is one.

Note from **his own last ~5 messages in this conversation**: lowercase or capitalised, emoji or none,
swearing or none, burst rhythm. Mirror them. (Case is predicted correctly 75% of the time from the previous
message, against 62% for always guessing lowercase.) If he has written nothing in the thread, use the
register's defaults.

Refuse and route to `haude` if the room is `#real-agent-only`, `#agents-only`, or the other party is a
colleague's agent.

### 3. Pick the register

From `AUDIENCES`: the person, or the room. Unknown internal and friendly: Wider. External or ILG-facing:
Channels, capitalised, no swearing. If Harry names a tone ("make it warmer", "keep it short"), follow him over
the table. Swearing only if **all** of the guide's conditions hold.

### 4. Draft

- Say all of the point, add no other facts. If a needed fact is missing, put a visible `[??]` and say so.
  Never invent a date, ETA, name or commitment.
- Shortest form that does the job. Terse readers: a few words. Bursts of 1 to 3 messages where it is chat.
- Answer the question that was asked and only that. Do not praise, restate or survey everything said.
- Take a stance if he has one. Emoji last, by the budget in `CORE` (default none).
- At most one stock wrapper (thanks, cheers, nickname, praise word), and only if the thread calls for it.

### 5. Lint

```bash
python3 ~/.claude/skills/voice/check.py --register <terse|warm|channels> [--swear-ok] <<'EOF'
first message
---
second message
EOF
```

Errors are the hard rules (em dash, closing full stop, `into`, `anyone`, `okay`, formal wording, bullets,
Unicode emoji, dropped apostrophes, `!!`, swearing). Fix every error. Fix warnings unless there is a reason.
Map register: Terse and Up (Oli) are `terse`; Reports and Wider are `warm`; everything in rooms is `channels`.

### 6. Show it

````
**Register:** terse (Jack) · mirrored: lowercase, no emoji

```text
first message
---
second message
```
````

Messages separated by `---` go out as separate Slack messages. Then one line: anything flagged `[??]`, any
reason the draft is thinner than usual, and "shorter variant?" only if it is over about 25 words. Do not
explain the style choices at length.

## Sending

**Never send.** If Harry asks for it saved, use `slack_send_message_draft` (one attached draft per
channel, and it holds a single message, so join a burst with a line break or leave it as chat text). Use
`thread_ts` for a thread reply. A `draft_already_exists` error means he has a draft there already: tell him.
Posting is always Harry's act. `slack_send_message` is not used by this skill.

## Weak spots: say so when you hit one

- Corrective feedback, escalation, refusals, incident and customer-facing voice: barely in the data. Flag the
  draft as a guess.
- ILG-facing and go-live rooms (late 2026): lower confidence, some evidence may be agent-written.
- Per-person rules for Schuster, Harry Humby, Wolf, John Finney, Oliver Wilders, Chris Mulder: under 60
  messages each. Use the register defaults.
- Email, PR comments, Jira, Confluence: not covered. Say so and offer a plain draft with no voice claims.

## Keeping the guide honest

- Re-mine when the terse or warm numbers drift by more than about 10 points, or roughly each quarter:
  `~/.claude/skills/voice/refresh/README.md`.
- If Harry edits a draft heavily, ask what changed and whether it is a one-off or a rule. Add real rules to
  `Voice/Voice.md` with the count that backs them, never from one example.
