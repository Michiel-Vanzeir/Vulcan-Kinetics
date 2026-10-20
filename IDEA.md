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
| **What** | A local capture agent (plus an optional browser extension) that notices when you hesitate while writing, or opens on a shortcut, and shows which colleagues know the topic, with trust signals. Raw text never leaves your machine. |
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

1. **Push, not pull.** The user never goes to a search page. Expertise comes to them in whatever app they're already writing in: mail, Teams, Slack, Word, a ticket.
2. **Trust signals, not just names.** Every suggested expert shows how recently and how fluently they worked on the topic, what they authored, and who implicitly vouches for them. Old expertise is labelled as old.
3. **Expertise learned from how people write, not from profiles.** The same typing signal that detects doubt also detects confidence: someone who writes fluently about a topic, answers questions on it, and authors documents about it knows it.
4. **Local-first privacy.** Keystrokes are processed on the employee's machine. Only small derived events (topic ids, signal, fluency) cross the network. No sentences, no names, no content.
5. **Consent built in.** Opt-in per app (surface), opt-out per topic. The topic opt-out is enforced in the backend, not just hidden in the UI.
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
2. They start struggling (see **Signal detector**), or press the shortcut.
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
| 2 | Capture agent: ring buffer + accessibility-API surface ids, password fields skipped, numbers/emails stripped | in progress (Michiel) | Michiel |
| 3 | Capture agent: signal detector (TYPING / HESITATING / STRUGGLING state machine per text field) | in progress (Michiel) | Michiel |
| 4 | Capture agent: trigger-based topic extractor against the fixed payroll vocabulary | in progress (Michiel) | Michiel |
| 5 | Capture agent: single, auditable send path emitting derived payloads | in progress (Michiel) | Michiel |
| 6 | Capture agent: Teams desktop watched end-to-end on one OS | in progress (Michiel) | Michiel |
| 7 | Manual hotkey trigger | in progress (Michiel) | Michiel |
| 8 | Fixed vocabulary of 200 to 500 payroll-domain topic ids | planned | |
| 9 | Backend `/analyze`: derived payload in, stored as event | planned | |
| 10 | Backend `/experts`: topic in, ranked experts + trust signals out, opt-out filtered | in progress (Sven) | Sven |
| 11 | Expertise scoring: fluency, artifact weight, peer vouches, recency decay, knowledge-gap threshold | planned | |
| 12 | Side panel with expert cards, evidence line, trust signals, "Ask [name]" | planned | |
| 13 | Browser extension as optional companion (richer in-browser context) | planned | |
| 14 | Consent UI: opt-in per surface, opt-out per topic | planned | |

---

## Architecture

System diagram: [`docs/Structure.png`](docs/Structure.png). More team reference material lives in `docs/`.

```
USER'S MACHINE                  LOCAL CAPTURE AGENT                       whoknows BACKEND
Gmail, Teams, Outlook,  keys    1. Ring buffer (~4 KB, in memory)
Word, Slack, Notion,   ------>  2. Signal detector (state per text field)
native apps                     3. Topic extractor (on triggers only)
                                4. Discard raw text
                                   { user_id, topics, signal,      --->   /analyze  (store event)
                                     surface, fluency, ts }               /experts  (rank people)
                                Side panel  <------------- ranked experts -------'
```

**Why a local agent and not add-ins per app:** one installer covers every writing surface. No separate Chrome extension, Office Add-in, Teams app or Slack app to deploy. IT ships one signed MSI or PKG through its existing MDM. The browser extension stays as an optional companion for richer in-browser context, but the agent works without it.

The capture agent is the data source for the expertise graph. It has two jobs:

1. Detect hesitation in real time, so the side panel can surface experts at the moment of doubt.
2. Emit expertise signals continuously, so the backend learns who actually knows what.

### Capture agent spec

**Capture buffer**
- Fixed-size ring buffer (about 4 KB), overwritten in place when full, so memory use stays constant.
- Each entry holds a character, a timestamp and a surface id. The surface id ties keystrokes to the focused app and text field via the OS accessibility API.
- Password fields detected via the accessibility API (`kSecureTextField` on macOS, `ES_PASSWORD` on Windows) are skipped entirely.
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
- Matches against a fixed vocabulary of 200 to 500 payroll-domain terms (e.g. `notice_period`, `PC_200`, `year_end_bonus`, `country_ES`, `meal_vouchers`) using substring and stem matching, plus a small named-entity pass for countries and PC numbers.
- Output is a subset of the vocabulary, never free text. The sentence never leaves memory.

**Signal detector**

Hesitation lasts longer than one window, so detection is stateful per focused text field.

| State | Meaning | Entered when |
|---|---|---|
| `TYPING` | Baseline, no signal | Start; or resolution (below) |
| `HESITATING` | Soft signal, nothing surfaced | Pause > 800 ms while TYPING |
| `STRUGGLING` | Payload emitted, side panel opens | HESITATING escalates (below) |

- **Escalation** (HESITATING to STRUGGLING) on any of: another pause within 10 s, a deletion burst, a hedge word, or still on the same sentence after 15 s.
- **Resolution** (back to TYPING) when the sentence is completed and sent, or after > 20 s of fluent typing.
- Each focused text field has its own state. Switching apps pauses that state; returning resumes it. Clearing or sending the field resets it.

**What crosses the network**

Only derived payloads, about 200 bytes per event. No sentences, no names, no content.

```json
{
  "user_id": "u_1234",
  "topics": ["notice_period", "country_ES"],
  "signal": "struggling",
  "surface": "outlook_desktop",
  "fluency": 0.3,
  "ts": 1729512345
}
```

The code path from keystrokes to network is **one function, auditable in a single file**. Local-first processing is an architectural guarantee, not a promise.

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

- Browser extension plus a thin desktop agent on **one OS** (macOS preferred: the on-screen permission prompts reinforce the consent story).
- Watch **one native app end-to-end: Teams desktop** (highest symbolic value for SD Worx).
- Everything else (Outlook, Word, Slack, Notion, Windows support, MDM installer, artifact ingestion from Confluence/Jira) lives as architecture on the slide.

## Non-negotiables

- **Raw text never leaves the machine.** Only derived payloads cross the network. Password fields are never captured. Numbers and email addresses are stripped before extraction.
- **One auditable send path:** all network calls from the agent go through a single function in a single file.
- **Security (10%):** check authorisation server-side on every ID (IDOR is the obvious risk in a tool that exposes data about colleagues). Keep API keys in environment variables, never in the repo. Keep the endpoint surface small. Run Aikido early.
- **Consent:** opt-in per surface, default off for personal browser profiles, banking and anything outside work. Opt-out per topic is filtered in the backend.
- **Honesty in the UI:** show stale or weak expertise as stale or weak. Never present a guess as certainty.
- **Show only what works:** the pitch, deck and description must not claim features that aren't `done`.
- **Demo without our own device:** every key moment must be capturable as a screenshot or short recording.

## Not building

Deliberate boundaries. Don't build these, even if they seem like a quick win.

- Per-app add-ins (Office Add-in, Teams app, Slack app). The local agent replaces them.
- Native capture for apps other than Teams desktop during the hackathon (slide only).
- Sending, storing or logging raw typed text anywhere, including debug logs.
- Routing incoming info@ emails to the right person (same engine, different input; mention it as a future extension in the pitch only).

## Open decisions

- Agent OS: the spec prefers macOS, but at least one teammate is on Windows. Decide which machine runs the demo.
- Agent language/runtime: _TBD_.
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
- 2026-10-20 (Michiel): Pivot from browser-only extension to a local capture agent covering all apps, with the extension as optional companion. Raw text stays on the machine; only derived payloads go to the backend. Hesitation detection is now a per-field state machine. Expertise is now inferred from fluency, answer direction, artifacts and implicit vouches; explicit "vouch on helpful answer" replaced by implicit vouches. Dropped the boundary against inferring expertise from behaviour, since the new design does exactly that, with local-first processing and per-surface consent as the safeguards. Demo: macOS agent watching Teams desktop.
- 2026-10-20 (Sven): Backend stack decided: Flask + Neo4j (the `Neo4J-backend/` code), dropped the FastAPI-or-Flask / Neo4j-or-JSON open decision. Package manager for the backend is uv. Added a Client node type (projects serve clients, knowledge can be about a client, clients hold nothing) and knowledge revisions (edits stored as a new version that supersedes the old one). Document-to-graph ingestion is still unbuilt; a local-Ollama plan is written up in `Neo4J-backend/README.md`.
