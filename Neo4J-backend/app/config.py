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

# --- who-knows ranking knobs (all pure maths, no model calls) ---
RECENCY_HALF_LIFE_DAYS = 180    # a knowledge item's recency weight halves after this many days
KEYWORD_BOOST = 0.3            # added per query term found in a doc's keywords, capped at +1.0
PING_PENALTY_STRENGTH = 0.25   # how hard an over-pinged person is down-weighted (0 = off)
WHO_KNOWS_PING_TOP_N = 1       # how many of the ranked experts are counted as "pinged" per query
KNOWLEDGE_GAP_MIN_SIMILARITY = 0.1   # best match weaker than this -> report a gap, not a weak name
