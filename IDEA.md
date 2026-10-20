# IDEA.md: whoknows

*Expertise finds you, not the other way around.*

Read this before working on the codebase. It describes **what we are building and why**.
The **Features** table tracks status; for exact behaviour, check the code and `README.md`.
Maintenance rules are in `AGENTS.md`, section 7. In short:

- Only real scope goes in this file. When a feature is dropped, delete it from **Features** completely.
- **Not building** lists deliberate boundaries so nobody (human or AI) builds them by accident.
- **Open decisions** lists what is still undecided. Remove an item once it's decided and log the decision in the changelog.
- **Changelog** is history only. It is never a to-do list.

---

## At a glance

| | |
|---|---|
| **What** | A local capture agent that notices when you hesitate while writing, or opens on a shortcut, and shows which colleagues know the topic, with trust signals. Raw text never leaves your machine. |
| **Challenge** | SD Worx, Tectonic Hackathon finals: *"Can your solution stay trusted without becoming another task?"* |
| **Deadline** | **16:00 sharp** on 2026-10-20 (hacking 09:00 to 16:00). |
| **Deliverables** | Builderbase: short description, pitch deck (ppt/pdf), public GitHub repo link, screenshots of final Aikido scan. |
| **Pitch** | 3 min in person + 5 min questions. **Not from our own device**: demo lives in the deck as screenshots or an embedded recording. |

### Scoring

| Criterion | Weight | What it means for us |
|---|---|---|
| Creativity | 25% | Push-not-pull, trust signals and fluency-as-expertise are the hook. Make them visible. |
| Pitch quality | 25% | Equal to creativity. Reserve real time for the deck and rehearsal. |
| Technical ability | 20% | It has to work, but a reliable demo beats extra features. |
| Fit with challenge | 20% | Use the extra-challenge table below, honestly. |
| Security (Aikido) | 10% | Scan early, fix, scan again before 16:00. |

---

## The problem

In a large organisation, knowledge lives mostly in people, not documents. A document search returns ten answers but doesn't tell you which one to trust. People finders tell you who might know something, but not whether that knowledge is still current. Expertise directories go stale because nobody keeps their profile up to date. The real moment of need comes while you're writing something and realise you're not sure.

## Context: SD Worx

SD Worx is a European HR and payroll company (10,000+ employees, payroll in 100+ countries), so the examples use payroll: year-end bonuses, joint committees like PC 200, and notice periods per country.

Original challenge: turn fragmented organisational knowledge into a trusted shared resource ("Find it. Understand it. Trust it.").

The finals extra challenge asks that the solution stay useful, reliable and up to date **without** people constantly documenting or maintaining it. Concretely:

- automate what can reasonably happen in the background,
- use human verification only where judgement adds real value,
- ask for minimal effort and attention,
- fit naturally into existing ways of working,
- stay almost invisible when things work, and be clear when people need to understand, decide or act.

SD Worx points beyond documents: the most useful answer is often *who* has dealt with this before. Their examples are a new developer asking "how do we do this here, who should I talk to?" and a marketer asking "who has done this before, what actually worked?"

> *Find it. Understand it. Trust it. Keep it trusted. Make it transparent. Make it effortless.*
> "The goal is not zero human involvement. The goal is zero unnecessary effort."

We are one of 32 finalist teams (out of 800+ participants).

---

## The core idea

1. **Push, not pull.** The user never goes to a search page. Expertise comes to them in whatever app they're already writing in, desktop or browser: Gmail, Outlook, Teams, Slack, Word, a ticket.
2. **Trust signals, not just names.** Every suggested expert shows how recently and how fluently they worked on the topic, what they authored, and who implicitly vouches for them. Old expertise is labelled as old.
3. **Expertise learned from how people write, not from profiles.** The same typing signal that detects doubt also detects confidence: someone who writes fluently about a topic, answers questions on it, and authors documents about it knows it.
4. **Local-first privacy.** Keystrokes are processed on the employee's machine. Only small derived events (topic ids, signal, fluency) cross the network. No sentences, no names, no content.
5. **Consent built in.** Opt-in per app (surface), opt-out per topic. Personal pages, private windows, passwords and other sensitive fields are never captured. The topic opt-out is enforced in the backend, not just hidden in the UI.
6. **Knowledge gap.** When nobody has recent expertise on a topic, whoknows shows a gap instead of a weak name.

### How whoknows answers the extra challenge

| SD Worx asks | whoknows |
|---|---|
| Automate what can happen in the background | The capture agent turns everyday writing into expertise signals: fluency, who answers whom, authored artifacts. Nobody fills in a profile. |
| Verify when human judgement adds value | Verification is implicit: when A asks about X, B answers, and A doesn't ask again for a week, that counts as a vouch for B. Stale expertise decays automatically through the recency term. |
| Minimise effort and attention | Invisible until the user is struggling. Otherwise one shortcut. |
| Integrate into existing ways of working | One local agent covers every writing surface. No new app, no per-app add-ins. IT deploys one signed installer via its existing MDM. |
| Make it understandable when people need to act | Every suggestion says *why*: the evidence, how old it is, and who vouched. Stale or weak expertise is labelled as such. |
| Think beyond documents | The answer is a person and the reason to trust them, not another document. |

**Keep this table honest.** Before the pitch, check every row against the **Features** table. Only claim what has status `done`; present the rest as architecture.

---

## User flow

1. The user is writing in any app: a Teams reply, an email, a section of a document.
2. They start struggling (the backend's **Scoring module** decides this from the detector's signals), or press the shortcut.
3. A side panel slides in with one card per detected topic.
4. Each card shows the top expert, one line of evidence ("answered this 12 times, last 2 weeks ago"), trust signals, and an "Ask [name]" action.

Example: Sarah De Vos (recent, fluent, vouched for) ranks above Tom Janssens (wrote the original procedure but hasn't touched the topic since 2024).

When there's no doubt, the panel stays out of the way: no badges, no notifications, nothing to maintain. A single pause is not enough to open it; only escalation to STRUGGLING is.

---

## Features

Only real scope. Status: `planned`, `in progress (name)`, `done`.

| # | Feature | Status | Owner |
|---|---|---|---|
| 1 | Synthetic dataset: 15 to 20 employees with the demo patterns (fresh expert, stale expert, opted-out person, knowledge-gap topic) | planned | |
| 2 | Capture agent: ring buffer + accessibility-API surface ids, password and sensitive fields skipped, numbers/emails stripped | done | Michiel |
| 3 | Capture agent: signal detector (raw signal counts per trigger, per text field; see "Signal detector output") | done | Michiel |
| 4 | Capture agent: trigger-based topic extractor against the fixed payroll vocabulary | done | Michiel |
| 5 | Capture agent: end-to-end pipeline (hook -> detector -> extractor -> backend format) and single, auditable send path (`agent/transport.py`) | done | Michiel |
| 6 | Capture agent surfaces: desktop apps (Teams, Outlook, Word, PowerPoint, OneNote, Slack, Notion) and work web apps in any browser (Gmail, Outlook, Teams, Google Docs, Slack, Notion, Confluence, Jira, SharePoint, Zendesk, Salesforce, ServiceNow) | in progress (Michiel) | Michiel |
| 7 | Manual hotkey trigger (Ctrl+Alt+W) | done | Michiel |
| 8 | Fixed vocabulary of payroll topic ids (35 topics + countries, PC numbers, worker classes for the demo) | done | Michiel |
| 9 | Backend `/analyze`: signal payload in, validated, handed to the expertise filter; `/experts`: topic tokens in, ranked experts out (`Neo4J-backend/app/signals.py`) | done | Michiel |
| 9b | Backend scoring module: TYPING / HESITATING / STRUGGLING state per text field, from signal payloads | planned | _teammate TBD_ |
| 10 | Backend `/experts`: topic in, ranked experts + trust signals out, opt-out filtered | in progress (Sven) | Sven |
| 11 | Expertise scoring: fluency, artifact weight, peer vouches, recency decay, knowledge-gap threshold | planned | |
| 12 | Side panel with expert cards, evidence line, trust signals, "Ask [name]" | planned | |
| 13 | Consent UI: opt-in per surface, opt-out per topic | planned | |
| 14 | Local webpage reproducing the reference settings popup and searchable people panel, with synthetic cards, simulated conversations, saved toggle and connection-state testing | done | Thoma |
| 15 | Local preview account availability: saved ping opt-out, 50-minute DND, profile availability and simulated ping actions | done | Thoma |

---

## Architecture

System diagram: [`docs/Structure.png`](docs/Structure.png). More team reference material lives in `docs/`.

```
USER'S MACHINE                  LOCAL CAPTURE AGENT                       whoknows BACKEND
Gmail, Teams, Outlook,  keys    1. Ring buffer (~4 KB, in memory)
Word, Slack, Notion,   ------>  2. Signal detector (raw counts per trigger,
native apps                        per text field)
                                3. Topic extractor (on triggers only)
                                4. Discard raw text
                                   signal payload (counts,          --->  /analyze: scoring module
                                   categories, topic ids)                   (TYPING / HESITATING /
                                                                            STRUGGLING) + expertise graph
                                                                          /experts  (rank people)
                                Side panel  <------------- ranked experts -------'
```

The agent measures; the backend interprets. The detector only counts things (pauses, deletions, hedge words, ...). The backend's scoring module turns those counts into a hesitation state and expertise scores. Doing it this way means expertise scoring can use raw signals across sessions, and the state machine can be retuned by replaying stored payloads. Privacy is the same either way, because the payload holds only counts and categories.

**Why a local agent and not add-ins per app:** one installer covers every writing surface, desktop apps and browsers alike. No Chrome extension, Office Add-in, Teams app or Slack app to deploy. IT ships one signed MSI or PKG through its existing MDM.

The capture agent is the data source for the expertise graph. It has two jobs:

1. Detect hesitation in real time, so the side panel can surface experts at the moment of doubt.
2. Emit expertise signals continuously, so the backend learns who actually knows what.

### Capture agent spec

**Capture buffer**
- Fixed-size ring buffer (about 4 KB), overwritten in place when full, so memory use stays constant.
- Each entry holds a character, a timestamp and a surface id. The surface id ties keystrokes to the focused app and text field via the OS accessibility API.
- **What gets captured:** opted-in desktop work apps, and browser tabs only when the window title shows a known work web app (Gmail, Outlook, Teams, ...). Any other page (banking, shopping, personal sites), private/incognito windows and personal browser profiles are never captured. When the focused field can't be identified, the keystroke is dropped (fail closed).
- Password fields detected via the accessibility API (`kSecureTextField` on macOS, `ES_PASSWORD` / UIA `IsPassword` on Windows) are skipped entirely.
- Other sensitive fields are skipped too: fields whose label or id mentions credentials (PIN, verification code, ...), payment cards, bank accounts or national ids (in EN/NL/FR/DE), plus the browser address bar.
- Numbers and email addresses are stripped from the window before extraction runs.

**Topic extractor**
- Runs on triggers only, not on every keystroke. Expect 5 to 15 runs per minute of active typing.
- Triggers:
  - natural pause > 800 ms
  - deletion burst: > 3 backspaces within 500 ms
  - punctuation: `.` `?` `!` or newline
  - hedge word appended to the buffer ("I think", "not sure", "probably", "denk ik", "volgens mij", ...)
  - manual hotkey
  - idle flush every 10 s if nothing else fired
- Lives in `capture-agent/topic_extractor/`: one pure function, `extract_topics(window, lang_hint=None)`, which the signal detector calls on each trigger to fill `topics`.
- Fixed vocabulary in `vocab.yaml` (EN/NL/FR): 35 payroll topics (e.g. `notice_period`, `year_end_bonus`, `meal_vouchers`), 15 countries (`country_ES`), joint committees (`PC_200`) and worker classes (`worker_white_collar`). Common misspellings in `typos.yaml`.
- Matching: Snowball stemming in the detected language (langdetect, trusted only for 60+ chars), exact matches in all languages for mixed-language text, long Dutch words inside compounds, and a named-entity pass for countries, PC numbers and worker classes. Patterns of 1 to 3 letters (`OR`, `RSZ`, `CDI`) only match in capitals. Numbers and emails are masked first.
- About 4 ms per 2000-char window. No model, no network.
- Output is a subset of the vocabulary, never free text, validated before returning. The sentence never leaves memory.

**Signal detector** (agent, `capture-agent/signal_detector/`)

- Turns a stream of keystroke events into **counted signals per compose context** (one focused text field in one app). It doesn't interpret them: no hesitation labels.
- Emits a signal payload when a trigger fires: pause > 800 ms, deletion burst (> 3 backspaces in < 500 ms), punctuation (`.` `?` `!` newline), a completed hedge word, a completed placeholder, idle flush every 10 s, manual hotkey, or the field being sent/cleared.
- Hedge words: about 300 phrases in EN/NL/FR/DE in `hedges.yaml`, matched on whole words when the word is completed. Matching ignores case, accents and apostrophes, and costs about 4 µs per check regardless of list size.
- Placeholders: `[...]`, `<...>`, `xxx` and longer, `???` and longer, and a trailing `...` followed by a pause > 2 s.
- Numbers and emails are masked before any lexical detection. They count toward total `chars_typed`, but never toward hedge words, placeholders or punctuation triggers.
- Pastes count only as `paste_events` and `pasted_char_count`, never as typing, fluency or lexical content.
- Password fields are hard-skipped from `focus_in` to `focus_out`: no state is created and nothing is emitted.
- State is kept per context. Switching focus pauses the context's state and returning resumes it. Sending or clearing the field resets it.
- Keeps a rolling per-user baseline (average pause, deletion rate), included once per session and whenever it shifts by more than 20%.

**Scoring module** (backend, teammate)

Consumes signal payloads and labels each compose context. Hesitation lasts longer than one payload, so the state is kept per context.

| State | Meaning | Entered when |
|---|---|---|
| `TYPING` | Baseline, no signal | Start; or resolution (below) |
| `HESITATING` | Soft signal, nothing surfaced | Pause > 800 ms while TYPING |
| `STRUGGLING` | Side panel opens with experts | HESITATING escalates (below) |

- **Escalation** (HESITATING to STRUGGLING) on any of: another pause within 10 s, a deletion burst, a hedge word, or still on the same sentence after 15 s.
- **Resolution** (back to TYPING) when the sentence is completed and sent, or after > 20 s of fluent typing.
- A `submit` payload resets the context.

### Signal detector output

This list is the detector's output (`SignalPayload`). Counters cover the period since the previous payload of the same context.

**On the wire** the agent sends the backend's format instead: `agent/backend_payload.py` turns each `SignalPayload` into the schema of `Neo4J-backend/expertise_filter.py` (counts **cumulative** since the context opened, `hedge_word` renamed `hedge`, topics accumulated per context), and `agent/transport.py` checks it before sending. That schema is the contract with the backend; the fields map one-to-one onto the groups below.

**Housekeeping**
- `schema_version`: payload format version
- `payload_seq`: increasing sequence number per agent run
- `ts`: unix ms when the payload was built
- `user_id`, `device_id`, `agent_version`, `os`: from agent config, constant per run

**Surface**
- `surface`: surface category, e.g. `outlook_desktop`, `gmail_web`
- `context_id`: opaque id of the compose context (focus session of one field)

**Timing**
- `trigger`: `pause` | `deletion_burst` | `punctuation` | `hedge_word` | `placeholder` | `idle_flush` | `manual` | `submit`
- `gap_before_trigger_ms`: time since the previous keystroke when the trigger fired
- `pause_count`: pauses > 800 ms
- `long_pause_count`: pauses > 2 s
- `longest_pause_ms`
- `mean_interkey_ms`: mean gap between keystrokes, gaps ≥ 10 s excluded (null if fewer than 2 keystrokes)
- `active_typing_ms`: sum of gaps < 800 ms

**Deletions**
- `backspaces`, `deletes`
- `deletion_bursts`
- `longest_deletion_run`: most consecutive deletion keys
- `rewrite_loops`: deleted 3+ chars, then typed again
- `deletion_rate`: deletions per typed char

**Fluency**
- `fluency_run_seconds`: length of the current uninterrupted typing run (no pause > 800 ms, deletion, hedge word or paste)
- `longest_fluency_run_seconds`

**Lexical**
- `chars_typed`: all typed chars, including masked numbers and emails
- `content_chars`: typed chars excluding masked tokens
- `masked_tokens`: number of number/email tokens masked
- `sentence_ends`: `.` `!` `?` or newline outside masked tokens
- `question_marks`
- `hedge_words`, plus `hedge_words_by_language`: counts per language code (`en`, `nl`, `fr`)
- `placeholders`, plus `placeholders_by_kind`: counts per `bracket`, `angle`, `x_run`, `question_run`, `trailing_ellipsis`
- `topics`: topic ids from the fixed vocabulary (empty until the topic extractor is wired in)

**Context**
- `is_reply`, `prior_message_char_count`: from the capture agent, when known
- `paste_events`, `pasted_char_count`
- `focus_switches`: times this context was left and resumed
- `focus_session_ms`: focused time in this context so far

**Baseline** (null unless included in this payload)
- `baseline_avg_pause_ms`, `baseline_avg_deletion_rate`

**Signals explicitly NOT sent**
- Typed characters, words or sentences, in any form (including hashes or fragments)
- Which hedge word or placeholder matched (only counts per language/kind)
- Pasted content, numbers, email addresses
- Window titles, URLs, field labels or names
- Per-keystroke timings (only aggregates)
- Clipboard or screen content

Example (about 600 bytes as JSON, nulls included):

```json
{
  "schema_version": 1, "payload_seq": 42, "ts": 1729512345000,
  "user_id": "u_1234", "device_id": "d_77", "agent_version": "0.1.0", "os": "windows",
  "surface": "outlook_desktop", "context_id": "c_9f2",
  "trigger": "hedge_word", "gap_before_trigger_ms": 140, "pause_count": 2,
  "longest_pause_ms": 1900, "mean_interkey_ms": 185.0, "active_typing_ms": 5200,
  "backspaces": 6, "deletes": 0, "deletion_bursts": 1, "longest_deletion_run": 4, "deletion_rate": 0.15,
  "fluency_run_seconds": 1.2, "longest_fluency_run_seconds": 4.8,
  "chars_typed": 44, "content_chars": 40, "masked_tokens": 1, "sentence_ends": 0, "question_marks": 0,
  "hedge_words": 1, "hedge_words_by_language": {"nl": 1}, "placeholders": 0, "placeholders_by_kind": {},
  "topics": [],
  "is_reply": true, "prior_message_char_count": 320, "paste_events": 0, "pasted_char_count": 0,
  "focus_switches": 1, "focus_session_ms": 31000,
  "baseline_avg_pause_ms": null, "baseline_avg_deletion_rate": null
}
```

The code path from keystrokes to network is **one function, auditable in a single file**: `build_payload()` in `capture-agent/signal_detector/detector.py` is the only producer of signal payloads, and `Transport._post()` in `capture-agent/agent/transport.py` is the only way out, after a wire-format check (known keys only, no free-text strings, topics only from the vocabulary). Local-first processing is an architectural guarantee, not a promise.

### Expertise graph (backend)

The agent only sees a sliding window. History lives in the backend, built from the event stream. For each (user, topic) pair the backend tracks frequency, recency, surfaces and signals.

Knowing versus talking about is the hard part: frequency alone surfaces the loudest person, not the most knowledgeable. The score combines four signals:

1. **Fluency.** The person wrote about the topic without hesitation, deletions or hedge words. This inverts the signal that drives hesitation detection.
2. **Direction of the conversation.** Who answers versus who asks, measured from message length ratio and reply direction via the accessibility API, without reading content. Answerers score; askers don't.
3. **Artifact authorship.** Wrote a Confluence page, closed a Jira ticket tagged with the topic, or authored a Word doc. Weighted much higher than chat mentions.
4. **Peer validation.** When A asks about X, B replies, and A doesn't ask again for a week, that is an implicit vouch for B on X. This drives the "who vouches for them" trust signal.

```
expertise(user, topic) = fluency * artifact_weight * peer_vouches * recency_decay

opted out of this topic         -> never returned
best score below threshold      -> "knowledge gap"
```

Stale knowledge decays automatically through `recency_decay`, which is how stale expertise gets shown as stale.

**Built so far** (`Neo4J-backend/`, Flask + Neo4j): the org hierarchy, the knowledge people
hold, clients, knowledge revisions, and `GET /who-knows` (semantic search ranked by person).
This is the substrate for the expertise graph. The whoknows scoring above (fluency, vouches,
recency decay, knowledge-gap threshold, per-topic opt-out) and document ingestion are **not**
built yet. Interface and the ingestion plan: `Neo4J-backend/README.md`.

### Synthetic data

A fictional payroll company of 15 to 20 employees with deliberate expertise patterns: one fresh expert, one stale expert, one opted-out person, one topic with no recent expertise. Every example comes from SD Worx's world (year-end bonuses, PC 200, notice periods per country). The backend is seeded with pre-generated event history and artifacts so the ranking has something to show.

**All data is synthetic.** Never use real or confidential data.

---

## Hackathon demo scope

- The capture agent alone (no extension) on **one OS**.
- Captures desktop work apps and work web apps in the browser. Lead the demo with **Teams** (highest symbolic value for SD Worx) and Gmail or Outlook.
- The rest (second OS, MDM installer, artifact ingestion from Confluence/Jira) lives as architecture on the slide.

## Non-negotiables

- **Raw text never leaves the machine.** Only derived payloads cross the network. Password and sensitive fields, personal pages and private windows are never captured. Numbers and email addresses are stripped before extraction.
- **One auditable send path:** all network calls from the agent go through a single function in a single file.
- **Security (10%):** check authorisation server-side on every ID (IDOR is the obvious risk in a tool that exposes data about colleagues). Keep API keys in environment variables, never in the repo. Keep the endpoint surface small. Run Aikido early.
- **Consent:** opt-in per surface; anything not on the work-surface list (personal browser profiles, banking, anything outside work) is never captured. Opt-out per topic is filtered in the backend.
- **Honesty in the UI:** show stale or weak expertise as stale or weak. Never present a guess as certainty.
- **Show only what works:** the pitch, deck and description must not claim features that aren't `done`.
- **Demo without our own device:** every key moment must be capturable as a screenshot or short recording.

## Not building

Deliberate boundaries. Don't build these, even if they seem like a quick win.

- A browser extension or per-app add-ins (Office Add-in, Teams app, Slack app). The local agent covers browsers and desktop apps.
- Sending, storing or logging raw typed text anywhere, including debug logs.
- Routing incoming info@ emails to the right person (same engine, different input; mention it as a future extension in the pitch only).

## Open decisions

- Agent OS: the spec prefers macOS; the agent is currently built for Windows (`capture-agent/surface_windows.py` is the only OS-specific file). Decide which machine runs the demo.
- Demo data: the expertise filter starts empty, so `/experts` returns nobody until people have sent payloads that score as answering with confidence. The synthetic dataset (feature 1) has to seed it, or `/experts` should also consult Sven's Neo4j graph.
- Reply detection: `is_reply`, `prior_message_char_count` and `question_marks_in_prior_message` are always false/0, because the agent doesn't read the message being replied to.
- Scoring formula: the product zeroes a score when any factor is 0 (e.g. no vouches yet). Each factor likely needs a floor (e.g. `1 + vouches`). Also decide where "direction of the conversation" enters the formula; it's listed as a signal but isn't a factor yet.

---

## Team & ownership

| Person | Area |
|---|---|
| Michiel | Capture agent + hesitation detection (features 2 to 7) |
| Sven | Neo4j backend: expertise graph, knowledge, who-knows (features 9 to 11) |
| _TBD_ | _TBD_ |
| _TBD_ | _TBD_ |

## Demo plan (3 min)

1. _TBD: problem in one sentence (the moment of doubt)._
2. _TBD: typing a Teams reply about notice periods in Spain, hesitating, panel opens showing Sarah above Tom, and why._
3. _TBD: privacy beat: what actually crossed the network (the 200-byte payload)._
4. _TBD: knowledge gap + opt-out respected._
5. _TBD: how it stays trusted with zero maintenance (extra-challenge table)._

## Submission checklist (before 16:00)

- [ ] **Delete `previous-round/` from the repo** (reference only; it would count in the Aikido scan).
- [ ] Final Aikido scan; screenshot showing repo name and remaining vulnerabilities.
- [ ] Repo is public; `README.md` has working setup and run steps; no secrets committed.
- [ ] Pitch deck (ppt/pdf) with demo screenshots or an embedded recording, tested on another machine.
- [ ] Every pitch claim matches a `done` feature.
- [ ] Builderbase: description, deck, repo link, Aikido screenshots.

---

## Branding

- **Name:** whoknows (lowercase). "Who knows?" is the thought at the moment of doubt.
- **Logo:** a text cursor and two white dots (typing, hesitating). The third dot becomes a yellow person (the colleague who knows).
- **Colours:** navy `#1B2A4E`, highlighter yellow `#FFD23F`, white `#FFFFFF`, muted blue-grey `#A0ACC8`.
- **Local popup previews:** SD Worx blue `#006DD8` and white, dark neutral text,
  with a restrained red `#F1002F` accent for stale expertise. Sans-serif text, compact corners,
  flat layouts and text labels instead of emoji icons. An information icon beside each name
  switches that card to an inline evidence view with a return action, without opening a popover.
  Profiles use light blue cards. Chats occupy the panel with back navigation that preserves
  the people search, draft messages and conversations during the preview session.
  A profile icon opens a separate account view. Ping opt-out and timed pauses share the
  same unavailable status on profile cards.
- **Typeface:** Bricolage Grotesque, extra bold for the wordmark.
- **Writing style:** plain, direct, no overclaiming, no em dashes.

## Project description (for Builderbase)

> Expertise finds you, not the other way around. whoknows notices when you hesitate while writing, in Teams, email or a document, or you can trigger it yourself with a shortcut. It then shows which colleagues have the expertise you need, with trust signals: how recent their expertise is, how fluently they write about it and who vouches for them. It learns from the work people already do, so nobody has to keep a profile up to date. Your text never leaves your machine: only topic labels do.

---

## Changelog

Format: `- YYYY-MM-DD HH:MM (name): what changed and why`. Append only, idea-level changes only.

- 2026-10-20 (Michiel): Created repo conventions (`AGENTS.md`, `CLAUDE.md`, `IDEA.md`).
- 2026-10-20 (Michiel): Added previous-round code in `previous-round/` as read-only reference. Starting fresh, not building on it.
- 2026-10-20 (Michiel): Finals idea set: whoknows, carried over from the previous round and extended for the SD Worx extra challenge (zero-maintenance trust: expertise from work signals, vouches, automatic decay). Added document writing as a trigger next to replies.
- 2026-10-20 09:55 (Thoma): Added a standalone popup preview for local UI testing without loading the previous-round extension.
- 2026-10-20 10:00 (Thoma): Extended the local preview with the reference people panel, searchable synthetic experts and simulated ask/reply/vouch interactions.
- 2026-10-20 10:14 (Thoma): Adopted blue and white for the local popup previews, with a flatter layout and clearer typography while retaining the existing interactions.
- 2026-10-20 10:21 (Thoma): Simplified the preview with neutral text, restrained SD Worx colour accents and expandable evidence to reduce visual clutter without removing functionality.
- 2026-10-20 10:28 (Thoma): Separated profiles with light blue cards and moved conversations into a dedicated panel view with back navigation to keep the people list easy to scan.
- 2026-10-20 11:34 (Thoma): Added local demo ping preferences, timed Do Not Disturb and recipient availability so the preview can demonstrate contact boundaries without real notifications.
- 2026-10-20 (Michiel): Pivot from browser-only extension to a local capture agent covering all apps, with the extension as optional companion. Raw text stays on the machine; only derived payloads go to the backend. Hesitation detection is now a per-field state machine. Expertise is now inferred from fluency, answer direction, artifacts and implicit vouches; explicit "vouch on helpful answer" replaced by implicit vouches. Dropped the boundary against inferring expertise from behaviour, since the new design does exactly that, with local-first processing and per-surface consent as the safeguards. Demo: macOS agent watching Teams desktop.
- 2026-10-20 (Sven): Backend stack decided: Flask + Neo4j (the `Neo4J-backend/` code), dropped the FastAPI-or-Flask / Neo4j-or-JSON open decision. Package manager for the backend is uv. Added a Client node type (projects serve clients, knowledge can be about a client, clients hold nothing) and knowledge revisions (edits stored as a new version that supersedes the old one). Document-to-graph ingestion is still unbuilt; a local-Ollama plan is written up in `Neo4J-backend/README.md`.
- 2026-10-20 (Michiel): Capture agent built in Python, Windows first (pynput + UI Automation), because that's the hardware we can test on. Joint committee numbers ("PC 200") are kept when numbers are scrubbed, since they are topics, not personal data.
- 2026-10-20 (Michiel): Dropped the browser extension: the capture agent is the only client. Agent now also captures browsers, limited to known work web apps (Gmail, Outlook, Teams, ...) by window title, plus more desktop apps (Outlook, Word, PowerPoint, OneNote, Slack, Notion). Sensitive fields (PIN, card, IBAN, address bar, ...), private windows and personal profiles are skipped.
- 2026-10-20 (Michiel): Split hesitation detection: the agent's signal detector now emits raw counts per trigger (no labels), and the TYPING/HESITATING/STRUGGLING state machine moved to a backend scoring module (teammate). The full signal payload is what crosses the network, so scoring can use signals across sessions and be retuned by replay. Added the "Signal detector output" contract (draft).
- 2026-10-20 (Michiel): Hedge list grown from about 30 to about 300 phrases and German added (SD Worx operates in DE). Matching is now spelling-tolerant (accents, apostrophes) and checked against neutral business sentences for false hits. Sensitive-field and private-window detection extended to NL/FR/DE labels and browser UIs; more work web apps recognised.
- 2026-10-20 (Michiel): Topic extractor built (`capture-agent/topic_extractor/`): keyword, stem and pattern matching against a fixed EN/NL/FR vocabulary of 35 payroll topics plus countries, PC numbers and worker classes. No ML model, so the output is provably a subset of the vocabulary. Not yet wired into the signal detector.
- 2026-10-20 (Michiel): Capture agent wired end to end: keyboard hook -> signal detector -> topic extractor -> backend wire format -> single sender, runnable with `python -m agent`. Adopted the backend's payload schema (expertise_filter.py, cumulative counts) as the wire format; added `placeholder` and `submit` to its accepted triggers, and long pauses and rewrite loops to the detector. Removed vocabulary patterns that fired on everyday sentences (notice, employee, manager, worker, index, ...). Enter sends in chat apps, Ctrl+Enter anywhere, Ctrl+Alt+W asks now.
- 2026-10-20 (Michiel): Agent and backend connected over HTTP. Agent: `agent/transport.py` (fire-and-forget POST /analyze with one retry, blocking POST /experts, optional bearer token, settings from env or `.env`). Backend: `/analyze` and `/experts` in `Neo4J-backend/app/signals.py` on the existing Flask app, Pydantic-validated (no free-text strings), feeding Daan's expertise filter. Ctrl+Alt+W now also prints who knows the field's topics.
