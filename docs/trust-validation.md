# Trust boundaries and validation

The prototype suggests colleagues using writing signals. It does not verify whether an
answer is correct. Fluency can reflect confidence, language proficiency or familiarity
with a keyboard; hesitation can reflect careful reasoning or accessibility needs. There
is no labelled real-world dataset, accuracy estimate or productivity study in this repo.
Synthetic regression tests establish software behaviour, not validity of these inferences.

## Implemented boundaries

- Desktop capture starts off. Employee-owned preferences persist in SQLite, and the agent
  uses an expiring consent cache. The backend rechecks consent when processing a signal.
- Browser processes are excluded. Window titles cannot establish origin or work profile.
- The hook validates surface and sensitivity before retaining characters. A bounded queue
  carries the validated field identity; changed focus, stale events and slow accessibility
  resolution cause drops. Raw buffers are cleared when focus or consent is untrusted.
- Backend requests require a server-configured bearer identity. Employee ingestion cannot
  impersonate a colleague. Graph administration requires a separate administrator token.
- Fixed topic ids are validated at the network boundary. Topic opt-out suppresses signal
  contributions and matching. Raw desktop text does not cross the agent network boundary.
- Explicit preview answers can provide reply metadata. Ordinary desktop typing cannot.
  Preview chats remain synthetic and local; demo feedback is not evidence of expertise.
- A context contributes at most its highest decayed confidence. Duplicate and old snapshots
  cannot add evidence. Contexts are scoped to employee, agent session and compose session.
  Suggestions require at least three distinct credited answer contexts and sufficient score.
- Every requested topic is retained. Missing matches remain gaps, including country gaps.
  A general topic match is not a qualification for every requested country or committee.

## Automated checks

Python tests cover authentication, identity spoofing, consent revocation, surface opt-in,
topic exclusion, vocabulary parity, replay protection, cross-employee context collisions,
thresholds, recency and the agent-to-Flask HTTP path. Node tests cover UI actions, backend
proxy origin checks, answer-count payload privacy and multi-topic gap display.

Run from the repo root:

```sh
uv run --project Neo4J-backend --with pytest --with-requirements capture-agent/requirements-dev.txt pytest Neo4J-backend/tests Neo4J-backend/test_expertise_filter.py capture-agent/tests -q
node --test preview-server.test.mjs preview-api.test.mjs preview-ui.test.mjs
```

## Validation still needed before deployment

Use independently labelled, consented examples of correct and incorrect answers, questions,
copied answers and unrelated fluent text. Include several writing speeds, languages and
accessibility tools. Hold out employees and topics when evaluating. Measure topic precision,
false interruption rate, reply classification, suggestion precision and knowledge-gap
recall. Compare against a directory-only baseline. No result is claimed until this study
is performed. Neither synthetic seed history nor passing unit tests substitutes for it.

Manually test Windows focus changes, password fields, personal accounts inside desktop
apps, accessibility-provider stalls and consent revocation. Process and field-label checks
cannot establish that every document inside an opted-in desktop app is work-related.
The synchronous accessibility check can drop keys on slow providers; this fails closed but
needs device testing. A Windows hook-level privacy audit and a fresh Aikido scan remain
required before submission or deployment.
