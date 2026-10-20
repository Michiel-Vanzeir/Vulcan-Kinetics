"""Idempotent: unique-id constraints + the vector index. Run once (and again any time, safely)."""
from app import config
from app.db import get_driver

STATEMENTS = [
    "CREATE CONSTRAINT orgnode_id IF NOT EXISTS FOR (n:OrgNode) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT knowledge_id IF NOT EXISTS FOR (k:Knowledge) REQUIRE k.id IS UNIQUE",
    f"""
    CREATE VECTOR INDEX knowledge_embedding IF NOT EXISTS
    FOR (k:Knowledge) ON (k.embedding)
    OPTIONS {{indexConfig: {{
        `vector.dimensions`: {config.EMBED_DIM},
        `vector.similarity_function`: 'cosine'
    }}}}
    """,
]

if __name__ == "__main__":
    with get_driver().session() as s:
        for stmt in STATEMENTS:
            s.run(stmt).consume()
        s.run("CALL db.awaitIndexes(60)").consume()
    print("Schema ready.")
