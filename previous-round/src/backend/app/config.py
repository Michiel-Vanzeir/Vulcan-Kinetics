import os
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "demo-password")

EMBED_BACKEND = os.getenv("EMBED_BACKEND", "sentence-transformers")
EMBED_MODEL = "all-MiniLM-L6-v2"
EMBED_DIM = 384  # fixed at vector-index creation; changing it means rebuilding the index

VECTOR_OVER_FETCH = 20   # fetched from the vector index before the superseded filter
WHO_KNOWS_DOCS = 5
WHO_KNOWS_PEOPLE = 5
