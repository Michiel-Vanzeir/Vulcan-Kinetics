# Who-knows graph demo (Neo4j + Flask)

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
```
