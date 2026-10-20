import atexit
from neo4j import GraphDatabase
from . import config

_driver = None


def get_driver():
    """One driver per process (thread-safe, pooled). Open a short session per operation."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        atexit.register(_driver.close)
    return _driver
