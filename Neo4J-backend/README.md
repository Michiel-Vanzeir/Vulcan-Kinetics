# whoknows backend (Neo4j + Flask)

The expertise graph behind whoknows (see `../IDEA.md`). It stores the org hierarchy, the
knowledge people hold, and the clients projects serve, and answers "who should I talk to?"
with semantic search over knowledge, ranked by person. `GET /who-knows` is the backend side
of the `/experts` idea in `IDEA.md`; the scoring there (fluency, vouches, recency decay) is
not built yet (see [Status](#status)).

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
| GET | `/who-knows?q=...` | `who_knows` |

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
subtree, and `/who-knows` semantic search ranked by person with their org paths.

**Stubbed / not built:**
- `app/extraction.py` (document to graph) is a stub that raises `NotImplementedError`.
  See [Document ingestion](#document-ingestion-not-built-yet).
- Ranking in `/who-knows` is `similarity * importance` only. The whoknows scoring in
  `IDEA.md` (fluency, peer vouches, recency decay, knowledge-gap threshold, per-topic
  opt-out) is **not** implemented.
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
