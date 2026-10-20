# whoknows backend (Neo4j + Flask)

The expertise graph behind whoknows (see `../IDEA.md`). It stores the org hierarchy, the
knowledge people hold, and the clients projects serve, and answers "who should I talk to?"
with semantic search over knowledge, ranked by person.

Two expertise paths live in this service, and they are separate on purpose:

- **Knowledge graph (`app/`, Neo4j):** `GET /who-knows?q=...` ranks people by the knowledge
  they hold that matches a text query. This is the document-driven answer.
- **Signal filter (`app/signals.py` + `expertise_filter.py`, SQLite):** `POST /analyze` and
  `POST /experts` serve the capture agent, scoring expertise from live typing signals
  (fluency, vouches, recency). The agent talks to this path.

The bridge between them is `Person.user_id` (the agent's `emp_*` id), set on graph people so
the same person can be referred to from either side. Unifying the two rankings is future work.

All data here is synthetic. Never load real or confidential data (AGENTS.md).

## Run plan

1. **Start Neo4j** (needs 5.18+ for vector indexes; compose file uses 5.26)
   ```bash
   docker compose up -d
   ```
   Browser UI at http://localhost:7474 (user `neo4j`, password `demo-password`).

2. **Python env** (managed by [uv](https://docs.astral.sh/uv/); Python 3.10-3.12, pinned to 3.12)
   ```bash
   uv sync                                             # creates .venv from uv.lock
   cp env.example .env                                 # Windows: copy env.example .env
   ```
   Then choose an embedding backend:
   - **Real embeddings:** `uv sync --extra ml` (large: installs torch; the first
     call also downloads `all-MiniLM-L6-v2`, ~90 MB).
   - **Quick wiring test:** set `EMBED_BACKEND=fake` in `.env` and skip the ML extra
     (word-overlap matching only, not semantic).

3. **Create schema** (idempotent)
   ```bash
   uv run schema.py
   ```

4. **Seed sample data** (`--reset` wipes the database first)
   ```bash
   uv run seed.py --reset
   ```
   Prints the Engineering department id for the subtree call below.

5. **Start the API**
   ```bash
   uv run run.py
   ```

6. **Try it**
   ```bash
   # who should I talk to?
   curl 'http://localhost:5000/who-knows?q=fraud+score+threshold'
   curl 'http://localhost:5000/who-knows?q=apple+pay+merchant'

   # org tree (replace <ID> with an id from seed.py output)
   curl 'http://localhost:5000/nodes/<ID>/subtree?depth=4'

   # knowledge rolled up to a node; include the superseded chain
   curl 'http://localhost:5000/nodes/<ID>/knowledge'
   curl 'http://localhost:5000/nodes/<ID>/knowledge?include_superseded=true'
   ```
   Expected: "fraud" queries return Alice first. The v1 and v2 fraud documents
   are superseded and will not appear unless `include_superseded=true`.

## Endpoints

| Method | Path | Function |
|---|---|---|
| POST | `/nodes` | `create_node` |
| POST | `/nodes/<id>/parents` | `link_node` (`{"parent_id": ...}`) |
| POST | `/nodes/<id>/clients` | `link_client` (`{"client_id": ...}`; Projects only) |
| GET | `/nodes/<id>/subtree?depth=3` | `get_subtree` |
| POST | `/knowledge` | `add_knowledge` (embeds title + summary + keywords itself) |
| POST | `/knowledge/<id>/revisions` | `revise_knowledge` (changed fields only; supersedes `<id>`) |
| GET | `/nodes/<id>/knowledge?recursive=true&include_superseded=false` | `get_knowledge_for_node` |
| GET | `/who-knows?q=...` | `who_knows` (ranked people; see [Ranking](#ranking)) |
| GET | `/pings` | `ping_counts` (people by how often they were surfaced; management view) |
| POST | `/analyze`, `/experts` | capture-agent signal path (`app/signals.py`, separate scorer) |

### Ranking

`GET /who-knows` scores each person as the sum, over their matching knowledge, of
`similarity * importance * recency * (1 + keyword_boost)`, then applies load balancing:

- **Recency** decays older knowledge (half-life `RECENCY_HALF_LIFE_DAYS`), so stale expertise
  ranks lower.
- **Keyword boost** adds a small bump for each query word that is also one of a document's
  keywords (hybrid lexical + vector; capped).
- **Load balancing (ping count):** every person has a `ping_count`. The query increments it for
  the top `WHO_KNOWS_PING_TOP_N` people it returns (the ones actually surfaced). Within a query,
  anyone whose count sits well above the other candidates' average is down-weighted a little
  (`PING_PENALTY_STRENGTH`), so repeated questions rotate across a close field instead of always
  hitting one person. Each result carries `ping_count` and `ping_penalty` (0 = none). A clearly
  dominant expert is only mildly reduced, not hidden. `GET /pings` exposes the counts for
  management ("who is the single point of contact for X").
- **Knowledge gap:** if the best match is weaker than `KNOWLEDGE_GAP_MIN_SIMILARITY`, the query
  returns `[]` rather than a misleading name. (Meaningful with the real `ml` embeddings; the
  `fake` backend gives every word some random overlap, so it rarely triggers there.)

All knobs live in `app/config.py`. None of this calls a model.

## Graph model

```
(:OrgNode:Person)-[:PART_OF]->(:OrgNode:Subteam|Team)-[:PART_OF]->...->(:OrgNode:Department)
(:OrgNode:Project)-[:SERVES]->(:OrgNode:Client)
(:OrgNode)-[:HAS_KNOWLEDGE]->(:Knowledge)-[:ABOUT]->(:OrgNode:Client)
(:Knowledge)-[:SUPERSEDES]->(:Knowledge)
```

Clients sit outside the `PART_OF` tree (no parents, no children) and cannot hold knowledge.
`GET /nodes/<client_id>/knowledge` returns the knowledge linked `ABOUT` that client.

## Example payloads

```bash
curl -X POST localhost:5000/nodes -H 'Content-Type: application/json' -d '{
  "type": "Team", "name": "Risk Ops", "summary": "Reviews flagged transactions.",
  "parent_ids": ["<PROJECT_ID>"]}'

curl -X POST localhost:5000/knowledge -H 'Content-Type: application/json' -d '{
  "title": "Manual review queue SLA", "summary": "Flagged transactions reviewed within 4 hours.",
  "keywords": ["fraud", "review", "sla"], "importance": 3,
  "occurred_at": "2026-09-01T10:00:00", "source_type": "slack", "source_uri": "slack://x",
  "holder_ids": ["<PERSON_ID>"], "client_ids": [], "supersedes_id": null}'

curl -X POST localhost:5000/nodes -H 'Content-Type: application/json' -d '{
  "type": "Client", "name": "Acme Retail", "summary": "Largest merchant."}'
curl -X POST localhost:5000/nodes/<PROJECT_ID>/clients -H 'Content-Type: application/json' -d '{
  "client_id": "<CLIENT_ID>"}'

# Revise: only changed fields. The rest is copied, occurred_at defaults to now,
# lists (keywords, holder_ids, client_ids) replace the old list. Returns the new item.
curl -X POST localhost:5000/knowledge/<KNOWLEDGE_ID>/revisions -H 'Content-Type: application/json' -d '{
  "keywords": ["fraud", "review", "sla", "escalation"], "holder_ids": ["<PERSON_ID>", "<TEAM_ID>"]}'
```

## Errors

All endpoints validate input and check every id server-side (IDOR is the main risk here):

| Code | When |
|---|---|
| 422 | Body fails schema validation, or a rule is broken (e.g. a Team under a Person, a Client used as a knowledge holder, an unknown field in a revision body). |
| 404 | A referenced node or knowledge id does not exist. |
| 409 | Revising or superseding an item that is already superseded. |

Error bodies are `{"error": "...", "details": ...}`.

## Status

What an integrator can rely on today, and what is still open.

**Works:** the org hierarchy, clients, knowledge with holders/clients/supersedes, revisions,
subtree, `/who-knows` semantic search with recency decay, keyword boost, ping-count load
balancing and knowledge-gap (see [Ranking](#ranking)), and `/pings` for the management view.
The capture-agent signal path (`/analyze`, `/experts`) is wired in `app/signals.py`.

**Stubbed / not built:**
- `app/extraction.py` (document to graph) is a stub that raises `NotImplementedError`.
  See [Document ingestion](#document-ingestion-not-built-yet).
- The graph ranking and the signal filter are two separate scorers; they are not unified, and
  `/who-knows` does not yet use fluency/vouches or per-topic opt-out.
- No read-by-id or delete/unlink endpoints yet. Ids come from `seed.py` output. To build an
  ingestion client you will likely want `GET /knowledge/<id>` and a node lookup by name.
- No auth. Fine for the local demo; note it before anything leaves localhost.

## Document ingestion (not built yet)

The missing piece is turning a raw source (email, Slack thread, PDF, Word doc) into a
`KnowledgeIn` payload, then calling `POST /knowledge` or `/knowledge/<id>/revisions`. This
fits whoknows' local-first rule: run the model on the user's machine, send only the derived
fields. Suggested shape for whoever picks this up (feature 9 area in `IDEA.md`):

1. **Extract with a local LLM (Ollama).** Prompt a small instruct model (e.g. `llama3.1:8b`
   or `qwen2.5:7b`) with Ollama's structured-output mode (`format` = a JSON schema matching
   `KnowledgeIn`) so it returns `title`, `summary`, `keywords`, `importance`, and the people
   and client it mentions. No free text leaves the box.
2. **Resolve names to ids.** Match mentioned people/clients to existing nodes by name, then
   fall back to embedding similarity. Unmatched names are a gap to surface, not a silent drop.
3. **New vs. revision.** Embed the draft and run `/who-knows` (or a direct vector query); if
   it is near-identical to an existing item the same person holds, call `/knowledge/<id>/revisions`
   instead of creating a duplicate.
4. **Embeddings.** Today the API embeds server-side (sentence-transformers or the `fake`
   backend). Ollama's `nomic-embed-text` is an alternative, but its vectors are 768-dim, so
   `EMBED_DIM` and the vector index in `schema.py` would have to change and the data be reseeded.

Keep the actual send path in one function (AGENTS.md: one auditable send path for anything
derived from user text).

## Layout

```
schema.py / seed.py     setup scripts
run.py                  Flask entry point
app/api.py              routes + error mapping
app/services.py        validation, hierarchy rules, embedding call, transactions
app/repository.py      all Cypher
app/hierarchy.py       node types + allowed parents + client-linkable types
app/models.py          pydantic request models (CreateNodeIn, KnowledgeIn, KnowledgeRevisionIn, ...)
app/embedding.py       embed() + build_knowledge_text()
app/extraction.py      stub for the LLM document reader (see Document ingestion)
```

## Capture-agent routes (`app/signals.py`)

`POST /analyze` takes one capture-agent payload (counts, flags, ids, topic tokens; see the
docstring at the top of `app/signals.py`), validates it with Pydantic and hands it to
`ExpertiseFilter.process()`. Its answer carries the filter's `doubt_alert` when the author is
struggling with the draft; the agent then opens the people panel. `POST /experts` takes `{"topics": [...]}` and returns the people the
filter rates as experts, best first. Free-text strings are rejected with 400. The filter's
SQLite store is `whoknows.db` (git-ignored; `WHOKNOWS_FILTER_DB` overrides) and is only used from
one dedicated thread, since SQLite connections can't be shared across Flask's request threads.

Tests: `uv run --with pytest pytest tests`.

## Expertise filter (`expertise_filter.py`)

A standalone, stdlib-only module that consumes payloads from the capture agent
(not in this repo) and decides when to route a tip to an expert. It is wired up
separately from the Neo4j graph so it can run on its own for the demo.

### Payload schema (summary)

Each payload is one trigger inside one focused text field. Every count is
**cumulative since the context opened**, so for a given `context_id` you take
the latest payload's values — never sum across payloads.

Fields: `user_id`, `context_id`, `ts` (Unix ms), `trigger`
(`pause|deletion_burst|punctuation|hedge|idle_flush|manual`), timing/pause
counts, deletions, fluency, hedge words and placeholders, question-mark counts,
window switches and pastes, `surface` (enum with `"other"` fallback),
`is_reply`, prior/current message char counts, baseline pause/deletion rate,
and `topics` (may be empty while the extractor is being built).

### Run

```bash
# From Neo4J-backend/
python -c "import expertise_filter as ef; \
  f = ef.build_filter('whoknows.db', 'directory.json'); \
  print(f.process({'user_id':'emp_014','context_id':'c1','ts':1,'trigger':'manual','topics':[]}))"
```

Tests:

```bash
pip install pytest
pytest test_expertise_filter.py -v
```

### Scoring model

Three scores are computed per snapshot (always the latest payload for that
`context_id`):

- **confidence_score**: `conf_base` plus fluency bonuses, minus penalties for
  deletions (normalised against the user's own `baseline_avg_deletion_rate`),
  deletion bursts, rewrite loops, hedges per 100 chars, placeholders, long
  pauses, window switches, and pause behaviour (normalised against
  `baseline_avg_pause_ms`). Multiplied by a paste discount
  `max(0, 1 - paste_ratio / 2*paste_discount_at_ratio)`.
- **doubt_score**: hedges, placeholders, question marks (heavier when not a
  reply), long pauses, deletion bursts, rewrite loops, and window switches
  relative to `context_age_ms`. Clipped to [0, 1].
- **direction**: `answering` when a long reply follows a short prior message
  with no question marks; `asking` for a short, non-reply, question-bearing
  message; `neutral` otherwise.

### Routing rules

- Expertise evidence is credited only when `direction == "answering"`,
  confidence is high, and paste ratio is low.
- Doubt evidence is credited when doubt is high (asker or not).
- Everyone is updated on every payload (asker and answerer alike) — the system
  tracks everyone, not just experts.
- `is_expert(user_id, topic)` combines profile relevance (seniority + title
  hints), recency-decayed expertise evidence, and surface breadth. Two vetoes:
  more doubt than expertise, or more pasted than authored content.
- `process(payload_dict, participants=None)` returns `None` when nothing is
  routable, or `{"tip": tip_or_none, "interactions": [...], "doubt_alert":
  alert_or_none}`.
  - `tip` — the routing dict for the side panel
    (`author`, `recipient`, `topic`, `score`, `reasons`).
  - `interactions` — edges in the shape `app/network.py` already consumes
    (`compose_answer` on answering, `asked_about` on asking). The network
    graph gets better passively from these without anyone filling in a
    profile. Empty when `participants` is `None`.
  - `doubt_alert` — the upstream push signal: *"this person is having
    doubts"*. Fires the moment doubt crosses `push_doubt_threshold`,
    respects `push_cooldown_ms` per context (so one hesitant draft doesn't
    spam the panel), and includes `user_id`, `context_id`, `surface`,
    `ts`, `doubt`, `topics` (may be empty — the panel can open before the
    topic extractor speaks), `direction`, and short human-readable
    `reasons`. Pass `on_doubt_push=callback` to the constructor to also
    receive the alert as a side-effect callback (true push semantics).
- Topics may be empty — the payload is then buffered under
  `pending_contexts[context_id]` and resolved on a later payload for the same
  context that carries topics.

All weights, thresholds, half-life, and veto ratios live in the top-level
`CONFIG` dict at the top of the file.

### Assumptions

- `recipient` is `None` unless the caller passes a `participants` list to
  `process()`. The payload itself identifies only one `user_id` (the author);
  the thread adapter (Outlook `to:`, Teams reply parent, meeting diarisation)
  is the one that resolves the counterparts and should pass them in.
- `baseline_avg_pause_ms` and `baseline_avg_deletion_rate` are sent once per
  session; the aggregator caches whichever baseline it has most recently seen
  for each `user_id` and never clears it from a later empty payload.
- Cumulative counts are reconciled with `max()` of the live snapshot and the
  stored total, so re-sending a payload (or a later payload for the same
  `context_id`) never double-counts pasted or authored characters.
- Decay half-life defaults to **30 days**; it mirrors `app/network.py`'s
  lazy-decay pattern but on millisecond timestamps.
- Surface breadth is `len(surfaces_seen) / len(SURFACES)`; the enum covers
  outlook/teams/gmail/word plus `other`.
- Payloads with unknown surfaces fall back to `other`; payloads with
  unknown triggers raise `ValueError` (the capture agent is in-house, so a
  bad trigger is a bug, not something to swallow silently).
- The SQLite file (`*.db`) is git-ignored; use `":memory:"` in tests.
- No capture / keylogging code: this module only consumes the payloads.
