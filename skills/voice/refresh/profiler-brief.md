# Brief: evidence-backed voice profile for ONE audience cluster

We are building a skill that drafts Slack replies in the voice of Harry Fitzgerald (engineering manager,
London, UK English). You are profiling how Harry writes to ONE audience cluster. Your profile is the
evidence base the skill will be written from, so accuracy beats flair. A wrong claim makes the skill
sound fake. Do not flatter, do not generalise beyond the data.

## Inputs (all under /tmp/claude-1000/-home-hjf-code-fuse/10181f4a-e6e7-4706-a6bb-3e49707e7bc1/scratchpad/voice/)
- `cluster-<name>.jsonl`: Harry's own human-typed Slack messages for your cluster, chronological.
  Keys: date, time, ch (channel / "DM:<person>" / "GDM:<people>"), kind, thread (true = a reply inside
  a thread), ts, text (verbatim, Slack markup kept, secrets already redacted).
  Machine-written messages (templated deploy/PR posts, agent digests, haude) were already removed.
- `analysis2.out`: baseline stats across ALL audiences, so you can say how your cluster differs.
- Read your WHOLE cluster file. Do not skim. (`python3` / `sed -n` in chunks of ~250 lines is fine.)
- Note: message rows are sampled from 52 random weekdays (Aug 2025 to Sep 2026), at most 120 messages per
  day, so heavy days are cut off after the first 120. Consecutive rows within a day are usually one
  conversation; Harry often sends several short messages in a row instead of one long one.

## What you may do on Slack (READ-ONLY)
Never send, draft, react or edit anything. To see what Harry was replying to, use the Slack tools
(load with ToolSearch `select:mcp__slack__slack_search_public_and_private,mcp__slack__slack_read_channel,mcp__slack__slack_read_thread`):
search `keywords` from his message text + `filters` "from:<@U0990E3P8BC> on:<date>" with
include_context=true shows surrounding messages and the channel id; then slack_read_channel with
`oldest`/`latest` a few minutes either side of the `ts` gives the exchange. Budget: at most ~30 context
fetches. Pick messages that are *replies to a request, question, problem, bad news, praise or thanks*,
not chit-chat. The point is to learn how the SITUATION shapes his reply.

## Evidence rules (strict)
1. Every quantitative claim must be computed with a script over the cluster file, not eyeballed. Show the
   number and n. Put your script at `profile-<name>.py` next to the output.
2. Every quoted example of Harry must be copy-exact from the cluster file (grep to confirm before you
   write it). Use his words, not a cleaned-up version.
3. Mark thin evidence: "(weak: n=3)". Do not write a rule from one or two instances.
4. A "never does X" claim needs a grep count of 0 (or near 0) over the cluster, and say so.
5. Other people's messages: paraphrase the situation in one line. Do not quote them verbatim.
6. SENSITIVE content must NOT appear in your deliverable, not even as an example: HR or performance
   matters about named people, health, family or other personal life details, money or salary,
   credentials or tokens, customer-confidential data, slurs. If a great example is sensitive, skip it and
   add a line "SENSITIVE-SKIP: <category>, n messages" to the section at the end.
7. Profanity: if he swears, record it as a feature of this cluster and how often, and say whether it
   would be wrong to use it outside this cluster. Do not reproduce slurs at all.

## Deliverable: `profile-<name>.md` with exactly these sections
1. **Who / relationship** (one line: role, how Harry relates, what the conversations are mostly about).
2. **Register in numbers**: median and p90 words, % starting lowercase, % ending in a full stop, use of
   "!", "?", emoji (which ones, and how often), ellipsis, dashes (" - " vs em dash), multi-message bursts,
   multi-line messages, links. Compare against the baseline in analysis2.out.
3. **Openers, acknowledgements and sign-offs**: the actual phrases, with counts.
4. **Recurring moves**, each with a count and 3 to 5 verbatim examples: how he asks, acknowledges, agrees,
   disagrees or pushes back, declines or defers, gives bad or awkward news, thanks, praises, jokes,
   delegates, offers help, chases, asks for an ETA, closes a thread. Only include moves that actually
   occur in this cluster.
5. **Lexicon and sentence frames**: signature words and constructions (British-isms, abbreviations,
   hedges like "I think" / "I believe", intensifiers, slang) with counts. Also words he does not use
   where that is informative.
6. **Situation → reply pairs**: 15 to 25 pairs. Format: `Situation (1-line paraphrase) → Harry: "<verbatim>"`.
   Choose for variety, and prefer ones where the situation clearly drove the wording.
7. **Longer messages (over ~25 words)**: how they are structured (context first or ask first, paragraphs,
   lists, sign-off), 3 verbatim examples.
8. **Anti-patterns**: things that would sound un-Harry for this cluster (formal phrasing, exclamation
   density, emoji he never uses, sentence types he never writes), each backed by a count.
9. **Drift**: does any feature change between Aug 2025 to Mar 2026 and Apr to Sep 2026 within this cluster?
   Numbers, with n per period.
10. **Confidence and gaps**: what you could not determine, what needs more data, SENSITIVE-SKIP lines.

## Final message back to the orchestrator (under 200 words)
File paths, the five features that most distinguish this cluster, anything surprising, and anything you
could not verify. No long quotes.
