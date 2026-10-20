# IDEA.md: whoknows

*Expertise finds you, not the other way around.*

Read this before working on the codebase. It describes **what we are building and why**.
The **Features** table tracks status; for exact behaviour, check the code and `README.md`.
Maintenance rules are in `AGENTS.md`, section 7. In short:

- Only real scope goes in this file. When a feature is dropped, delete it from **Features** completely.
- **Not building** lists deliberate boundaries so nobody (human or AI) builds them by accident.
- **Changelog** is history only. It is never a to-do list.

---

## At a glance

| | |
|---|---|
| **What** | Browser extension that notices when you hesitate while writing, or opens on a shortcut, and shows which colleagues know the topic, with trust signals. |
| **Challenge** | SD Worx, Tectonic Hackathon finals: *"Can your solution stay trusted without becoming another task?"* |
| **Deadline** | **16:00 sharp** on 2026-10-20 (hacking 09:00 to 16:00). |
| **Deliverables** | Builderbase: short description, pitch deck (ppt/pdf), public GitHub repo link, screenshots of final Aikido scan. |
| **Pitch** | 3 min in person + 5 min questions. **Not from our own device**: demo lives in the deck as screenshots or an embedded recording. |

### Scoring

| Criterion | Weight | What it means for us |
|---|---|---|
| Creativity | 25% | Push-not-pull and trust signals are the hook. Make them visible. |
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

1. **Push, not pull.** The user never goes to a search page. Expertise comes to them inside the tool they're already writing in: mail, tickets, chat, or a document.
2. **Trust signals, not just names.** Every suggested expert shows how recently and how often they worked on the topic, and which colleagues vouch for them. Old expertise is labelled as old.
3. **Consent built in.** Employees choose per topic whether they're findable. The opt-out is enforced in the backend, not just hidden in the UI.
4. **Knowledge gap.** When nobody has recent expertise on a topic, whoknows shows a gap instead of a weak name.

### How whoknows answers the extra challenge

| SD Worx asks | whoknows |
|---|---|
| Automate what can happen in the background | Expertise is built from signals that everyday work already creates: tickets resolved, documents written, questions answered in chat. Nobody fills in a profile. |
| Verify when human judgement adds value | The only human step is light and comes when it matters: if someone asks an expert through whoknows and the answer helps, that counts as a vouch. Stale expertise decays automatically. |
| Minimise effort and attention | Invisible until the user hesitates. Otherwise one shortcut. |
| Integrate into existing ways of working | A side panel in the tools people already write in. No new app. |
| Make it understandable when people need to act | Every suggestion says *why*: the evidence, how old it is, and who vouched. Stale or weak expertise is labelled as such. |
| Think beyond documents | The answer is a person and the reason to trust them, not another document. |

**Keep this table honest.** Before the pitch, check every row against the **Features** table. Only claim what has status `done`.

---

## User flow

1. The user is writing a reply or a section of a document.
2. They hesitate, or press the shortcut (optionally with text selected).
3. A side panel slides in with one card per detected topic.
4. Each card shows the top expert, one line of evidence ("handled this 12 times, last 2 weeks ago"), trust signals, and an "Ask [name]" action.

Example: Sarah De Vos (recent, frequent, vouched for) ranks above Tom Janssens (wrote the original procedure but hasn't touched the topic since 2024).

When there's no doubt, the panel stays out of the way: no badges, no notifications, nothing to maintain.

### Triggers

**Where:** anywhere the user writes in the browser.
- **Replying** to a customer or colleague (email, ticket, chat).
- **Writing a document** (procedure, client memo, proposal, campaign plan, shared notes). Doubting while drafting is enough; the user doesn't have to be answering anyone.

**Hesitation signals:**
- A 2 to 3 second pause mid-sentence after active typing.
- Typing and then deleting a word or sentence.
- Hedging language: "I believe", "I think", "not sure", "probably", "denk ik", "volgens mij".
- In documents: placeholders the writer leaves for themselves ("TBD", "check this", "??", "[ask someone]").

**Manual:** a keyboard shortcut opens the panel for the current text. With a passage selected, it answers "who knows about this part?".

---

## Features

Only real scope. Status: `planned`, `in progress (name)`, `done`.

| # | Feature | Status | Owner |
|---|---|---|---|
| 1 | Synthetic dataset: 15 to 20 employees with the demo patterns (fresh expert, stale expert, opted-out person, knowledge-gap topic) | planned | |
| 2 | Backend `/analyze`: text in, topics + hesitation signals out | planned | |
| 3 | Backend `/experts`: topic in, top 3 experts + trust signals out, opt-out filtered | planned | |
| 4 | Ranking: relevance + recency decay + frequency + vouches, with a knowledge-gap threshold | planned | |
| 5 | Extension content script on textarea / contenteditable | planned | |
| 6 | Hesitation detection (pause, delete, hedging words, placeholders) | planned | |
| 7 | Keyboard shortcut trigger (+ selected text) | planned | |
| 8 | Side panel with expert cards, evidence line, trust signals, "Ask [name]" | planned | |
| 9 | Vouch on helpful answer (feeds back into ranking) | planned | |
| 10 | Mock demo pages: mail, chat, contenteditable document | planned | |
| 11 | Per-topic opt-out UI for employees | planned | |
| 12 | Local webpage reproducing the reference settings popup and searchable people panel, with synthetic cards, simulated conversations, saved toggle and connection-state testing | done | Thoma |
| 13 | Local preview account availability: saved ping opt-out, 50-minute DND, profile availability and simulated ping actions | done | Thoma |

---

## Architecture

```
Chrome extension (Manifest v3)              Backend (Python, FastAPI or Flask: TBD)
- content script on the active text field   - /analyze: text in, topics + hesitation signals out
  (textarea, contenteditable)               - /experts: topic in, top 3 experts + trust signals out
- hesitation detection + shortcut           - expertise graph built from employee data (JSON)
- side panel rendering expert cards
```

- Topic matching uses embeddings against a fixed list of 20 to 30 topics, with keyword matching as the fallback if latency is a problem.
- Debounce requests (2 to 3 s) and cache the results.
- For documents, send the current paragraph or the selection, never the whole document.
- Real rich editors like Google Docs are hard to read from a content script, so the demo uses our own contenteditable mock pages.

### Ranking

```
score = relevance  (embedding match on evidence)
      + recency    (exponential decay over time)
      + frequency  (times handled)
      + peer       (times vouched for)

opted out of this topic         -> never returned
best score below threshold      -> "knowledge gap"
```

### Data model (example)

```json
{
  "id": "emp_014",
  "name": "Sarah De Vos",
  "role": "Payroll consultant",
  "country": "BE",
  "opt_in": true,
  "hidden_topics": [],
  "evidence": [
    {
      "type": "ticket",
      "topic": "year-end bonus PC 200",
      "text": "Calculated year-end bonus for part-time employee",
      "date": "2026-09-16",
      "vouched_by": ["emp_003", "emp_021"]
    }
  ]
}
```

Evidence types are `ticket`, `document`, `chat_answer` and `vouch`. All of them are things work already produces, which is the point of the extra challenge.

**All data is synthetic.** Never use real or confidential data.

---

## Non-negotiables

- **Security (10%):** check authorisation server-side on every ID (IDOR is the obvious risk in a tool that exposes data about colleagues). Keep API keys in environment variables, never in the repo. Keep the endpoint surface small. Run Aikido early.
- **Consent:** opt-out filtering happens in the backend.
- **Honesty in the UI:** show stale or weak expertise as stale or weak. Never present a guess as certainty.
- **Show only what works:** the pitch, deck and description must not claim features that aren't `done`.
- **Demo without our own device:** every key moment must be capturable as a screenshot or short recording.

## Not building

Deliberate boundaries. Don't build these, even if they seem like a quick win.

- Routing incoming info@ emails to the right person (same engine, different input; mention it as a future extension in the pitch only).
- Real integrations with Gmail, Outlook, Teams or Google Docs. The demo uses mock pages.
- Inferring "silent experts" from behaviour beyond explicit work evidence (GDPR).

---

## Team & ownership

| Person | Area |
|---|---|
| Michiel | _TBD_ |
| _TBD_ | _TBD_ |
| _TBD_ | _TBD_ |
| _TBD_ | _TBD_ |

## Demo plan (3 min)

1. _TBD: problem in one sentence (the moment of doubt)._
2. _TBD: hesitation in a mail reply leads to a panel showing Sarah above Tom, and why._
3. _TBD: shortcut on a selected passage in a document._
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

> Expertise finds you, not the other way around. Our browser plugin detects when you hesitate while writing, whether you're replying to a customer or drafting a document, or you can trigger it yourself with a shortcut. It then shows which colleagues have the expertise you need, with trust signals: how recent their expertise is, how often they've handled it and who vouches for them. It learns from the work people already do, so nobody has to keep a profile up to date.

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
