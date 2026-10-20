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
```
