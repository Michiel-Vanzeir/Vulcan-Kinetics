# IDEA.md: whoknows
 
*Expertise finds you, not the other way around.*
 
This file explains what we are building and why. Read it before working on the codebase. It describes the idea, not the current state of the code: check the repo and README for what is actually implemented.
 
## One-line summary
 
whoknows is a browser extension that notices when you hesitate while writing (a reply to a customer or colleague, or a document you are working on) or opens on a keyboard shortcut, and shows which colleagues know the topic, with trust signals that tell you how far to rely on them.
 
## Origin and current stage
 
Built for the SD Worx challenge at the Tectonic Hackathon. The original challenge: turn fragmented organisational knowledge into a trusted shared resource ("Find it. Understand it. Trust it."). SD Worx is a European HR and payroll company (10,000+ employees, payroll in 100+ countries), so most examples use payroll: year-end bonuses, joint committees like PC 200, notice periods per country.
 
We are now in the **finals** (32 teams out of 800+ participants). Hacking runs 09:00 to 16:00, submissions close at 16:00 sharp.
 
### Finals: SD Worx extra challenge
 
*"Can your solution stay trusted without becoming another task?"*
 
Knowledge changes, people change roles, expertise evolves. The solution has to stay useful, reliable and up to date without asking people to constantly document, update or maintain it. SD Worx asks for:
 
- automating what can reasonably happen in the background,
- human verification only where judgement adds real value,
- minimal effort and attention,
- fitting naturally into existing ways of working,
- being almost invisible when things work and clear when people need to understand, decide or act.
They explicitly point beyond documents: the most useful answer is often *who* has dealt with this before, who really knows this customer or topic, who knows how it actually works here and why. Their examples: a new developer asking "how do we do this here, who should I talk to?" and someone launching a marketing campaign asking "who has done this before, what actually worked?"
 
Their closing line: *Find it. Understand it. Trust it. Keep it trusted. Make it transparent. Make it effortless.* "The goal is not zero human involvement. The goal is zero unnecessary effort."
 
This extra challenge fits whoknows closely. Section "How whoknows answers the extra challenge" below is the design direction for the finals build.
 
### Finals scoring
 
| Criterion | Weight |
|---|---|
| Creativity: how original is the idea? | 25% |
| Pitch quality: how well did we present? | 25% |
| Technical ability: does it work? | 20% |
| Fit: did we solve the challenge? | 20% |
| Security: Aikido audit, remaining vulnerabilities | 10% |
 
Pitch format: in person, 3-minute pitch plus 5 minutes of questions, strict timing. We do **not** present from our own device, so the demo must work from a pitch deck (ppt or pdf) with screenshots or an embedded recording. Builderbase submission by 16:00: short description, pitch presentation, public GitHub repo link, and screenshots of the final Aikido scan showing the repo name and remaining vulnerabilities.
 
What this means for the build: pitch quality now weighs as much as creativity, and technical ability counts less than before. A clear, reliable demo that can be captured in screenshots or a short recording beats extra features.
 
## The problem
 
In a large organisation, knowledge lives mostly in people, not documents. Searching documents returns ten answers but does not tell you which one to trust, and people finders tell you who might know something but not whether their knowledge is current. Expertise directories also go stale, because nobody keeps their profile up to date. The real moment of need is when you are writing something and realise you are not sure.
 
## The core idea
 
Three choices make this different from a standard people finder:
 
1. **Push, not pull.** The user does not go to a search page. Expertise comes to them, inside the tool they are already writing in: mail, tickets, chat, or a document.
2. **Trust signals, not just names.** Every suggested expert shows how recently they worked on the topic, how often, and which colleagues vouch for them. An expert with old knowledge is shown as such.
3. **Consent built in.** Employees choose whether they are findable, per topic. Expertise is tracked automatically from their work, or manually if they prefer. Opt-out is enforced in the backend, not just hidden in the UI.
Optional: when nobody has recent expertise on a topic, show a **knowledge gap** instead of a name.
 
## Where it triggers
 
Anywhere the user writes in the browser:
 
- **Replying** to a customer or colleague: email, ticket, chat message.
- **Writing a document:** a procedure, a client memo, a proposal, a campaign plan, notes in a shared doc. The user does not have to be answering anyone; doubting while drafting is enough.
### Hesitation signals
 
- A pause of 2 to 3 seconds mid-sentence after active typing.
- Typing and then deleting a word or sentence.
- Hedging language: "I believe", "I think", "not sure", "probably", "denk ik", "volgens mij".
- In documents also: question marks or placeholders the writer leaves for themselves ("TBD", "check this", "??", "[ask someone]").
### Manual trigger
 
- A keyboard shortcut opens the panel for the current text.
- In a document, the user can select a passage and press the shortcut to ask "who knows about this part?".
## User flow
 
1. The user is writing: a reply, or a section of a document.
2. They hesitate, or press the shortcut (optionally with text selected).
3. A side panel slides in with cards per detected topic.
4. Each card shows the top expert, one line of evidence ("handled this 12 times, last 2 weeks ago"), trust signals, and an "Ask [name]" action.
Example: Sarah De Vos (recent, frequent, vouched for by colleagues) ranks above Tom Janssens (wrote the original procedure but has not worked on the topic since 2024).
 
The panel stays out of the way when there is no doubt: no badges, no notifications, nothing to maintain.
 
## How whoknows answers the extra challenge
 
| SD Worx asks | whoknows |
|---|---|
| Automate what can happen in the background | Expertise is built from signals that everyday work already creates: tickets resolved, documents written or edited, questions answered in chat. Nobody fills in a profile. |
| Verify when human judgement adds value | The only human step is light and happens at the moment it matters: when someone asks an expert through whoknows and the answer helps, that counts as a vouch. Stale expertise decays automatically instead of being cleaned up by hand. |
| Minimise effort and attention | Invisible until the user hesitates. One shortcut otherwise. |
| Integrate into existing ways of working | Lives as a side panel in the tools people already write in. No new app. |
| Make it understandable when people need to act | Every suggestion says *why*: the evidence, its age, who vouched. Stale or weak expertise is labelled as such. |
| Think beyond documents | The answer whoknows gives is a person and the reason to trust them, not another document. |
 
Keep this table honest: only claim in the pitch what the build actually does.
 
## Architecture
 
```
Chrome extension (Manifest v3)              Backend (FastAPI or Flask)
- content script on the active text field   - /analyze: text in, topics + hesitation signals out
  (textarea, contenteditable, doc editors)  - /experts: topic in, top 3 experts + trust signals out
- hesitation detection + shortcut           - expertise graph built from employee data (JSON)
- side panel rendering expert cards
```
 
- Topic matching: embeddings against a fixed list of 20 to 30 topics. Keyword matching is the fallback if latency is a problem.
- Debounce requests (2 to 3 seconds) and cache results.
- For documents, send the current paragraph or the selection, not the whole document.
- Rich editors like Google Docs render text in a non-standard way and are hard to read from a content script. For the demo, use a simple mock document page built on contenteditable rather than fighting a real editor.
### Ranking
 
```
score = relevance (embedding match on evidence)
      + recency bonus (exponential decay over time)
      + frequency bonus (times handled)
      + peer bonus (times vouched for)
opted out of this topic -> never returned
best score below threshold -> "knowledge gap"
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
 
Evidence types: `ticket`, `document`, `chat_answer`, `vouch`. All of them are things work already produces, which is the point of the extra challenge.
 
All data is synthetic: a fictional company of 15 to 20 employees with deliberate patterns (one fresh expert, one stale expert, one opted-out person, one topic with no recent expertise). Never use real or confidential data.
 
## Non-negotiables
 
- **Security (10%):** check authorisation server-side on every ID (IDOR is the obvious risk in a tool that exposes data about colleagues). No API keys in the repo; use environment variables. Keep the endpoint surface small. Run Aikido early so there is time for fixes and a final scan before 16:00.
- **Consent:** opt-out filtering happens in the backend.
- **Honesty in the UI:** show stale or weak expertise as stale or weak. Never present a guess as certainty.
- **Show only what works:** the pitch, deck and description must not claim features that are not implemented.
- **Demo without our own device:** every key moment must be capturable as a screenshot or short recording for the deck.
## Out of scope (for now)
 
- Routing incoming info@ customer emails to the right person. Same engine, different input; a natural extension, not part of the core.
- Real integrations with Gmail, Outlook, Teams or Google Docs. The demo uses mock mail, chat and document pages.
- Inferring "silent experts" from behaviour beyond explicit work evidence, because of GDPR concerns.
## Branding
 
- **Name:** whoknows (lowercase). "Who knows?" is the thought at the moment of doubt.
- **Logo:** a text cursor and two white dots (typing, hesitating); the third dot becomes a yellow person (the colleague who knows).
- **Colours:** navy `#1B2A4E`, highlighter yellow `#FFD23F`, white `#FFFFFF`, muted blue-grey `#A0ACC8`.
- **Typeface:** Bricolage Grotesque, extra bold for the wordmark.
- **Writing style:** plain, direct, no overclaiming, no em dashes.
## Project description
 
> Expertise finds you, not the other way around. Our browser plugin detects when you hesitate while writing, whether you are replying to a customer or drafting a document, or you can trigger it yourself with a shortcut. It then shows which colleagues have the expertise you need, with trust signals: how recent their expertise is, how often they handled it and who else vouches for them. It learns from the work people already do, so nobody has to keep a profile up to date.