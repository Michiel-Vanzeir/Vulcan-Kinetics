# Who-knows graph demo (Neo4j + Flask)

## Run plan

1. **Start Neo4j** (needs 5.18+ for vector indexes; compose file uses 5.26)
   ```bash
   docker compose up -d
   ```
   Browser UI at http://localhost:7474 (user `neo4j`, password `demo-password`).

2. **Python env** (use Python 3.10-3.12 and a fresh venv)
   ```bash
   python --version
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   cp .env.example .env                                # Windows: copy .env.example .env
   ```
   Then choose an embedding backend:
   - **Real embeddings:** `pip install -r requirements-ml.txt` (large: installs torch; the first
     call also downloads `all-MiniLM-L6-v2`, ~90 MB).
   - **Quick wiring test:** set `EMBED_BACKEND=fake` in `.env` and skip the ML install
     (word-overlap matching only, not semantic).

3. **Create schema** (idempotent)
   ```bash
   python schema.py
   ```

4. **Seed sample data** (`--reset` wipes the database first)
   ```bash
   python seed.py --reset
   ```
   Prints the Engineering department id for the subtree call below.

5. **Start the API**
   ```bash
   python run.py
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
| GET | `/nodes/<id>/subtree?depth=3` | `get_subtree` |
| POST | `/knowledge` | `add_knowledge` (embeds title + summary + keywords itself) |
| GET | `/nodes/<id>/knowledge?recursive=true&include_superseded=false` | `get_knowledge_for_node` |
| GET | `/who-knows?q=...` | `who_knows` |

## Example payloads

```bash
curl -X POST localhost:5000/nodes -H 'Content-Type: application/json' -d '{
  "type": "Team", "name": "Risk Ops", "summary": "Reviews flagged transactions.",
  "parent_ids": ["<PROJECT_ID>"]}'

curl -X POST localhost:5000/knowledge -H 'Content-Type: application/json' -d '{
  "title": "Manual review queue SLA", "summary": "Flagged transactions reviewed within 4 hours.",
  "keywords": ["fraud", "review", "sla"], "importance": 3,
  "occurred_at": "2026-09-01T10:00:00", "source_type": "slack", "source_uri": "slack://x",
  "holder_ids": ["<PERSON_ID>"], "supersedes_id": null}'
```

## Layout

```
schema.py / seed.py     setup scripts
run.py                  Flask entry point
app/api.py              routes + error mapping
app/services.py        validation, hierarchy rules, embedding call, transactions
app/repository.py      all Cypher
app/hierarchy.py       allowed parent types
app/embedding.py       embed() + build_knowledge_text()
app/extraction.py      stub for the future LLM document reader
expertise_filter.py    capture-agent signal consumer (SQLite, stdlib only)
directory.json         sample profile data (user_id -> job_title/seniority/dep)
test_expertise_filter.py pytest suite for the filter
```

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
  routable, or `{"tip": tip_or_none, "interactions": [...]}`. The `tip` is the
  routing dict for the side panel (`author`, `recipient`, `topic`, `score`,
  `reasons`). The `interactions` list is empty when `participants` is `None`;
  with participants, it carries edges in the shape `app/network.py` already
  consumes — `compose_answer` from author to each counterpart on an answering
  context, `asked_about` from each counterpart to the author on an asking
  context. The network graph gets better passively from these edges without
  anyone filling in a profile.
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
