"""All Cypher lives here. Every function takes a transaction and uses parameters only.
Labels / path lengths can't be parameters in Cypher, so they are validated before being formatted in."""
from collections import defaultdict
from .hierarchy import NODE_TYPES

_TYPE_EXPR = "[l IN labels({v}) WHERE l <> 'OrgNode'][0]"
_NODE_MAP = "{v}{{.id, .name, .summary, .email, .phone, type: " + _TYPE_EXPR + "}}"


def _node_map(v: str) -> str:
    return _NODE_MAP.format(v=v)


# ---------- org ----------
def get_types(tx, ids: list[str]) -> dict[str, str]:
    q = f"MATCH (n:OrgNode) WHERE n.id IN $ids RETURN n.id AS id, {_TYPE_EXPR.format(v='n')} AS type"
    return {r["id"]: r["type"] for r in tx.run(q, ids=ids)}


def create_node(tx, node_type: str, props: dict) -> None:
    assert node_type in NODE_TYPES
    tx.run(f"CREATE (n:OrgNode:{node_type}) SET n = $props", props=props)


def link(tx, child_id: str, parent_ids: list[str]) -> None:
    tx.run(
        """
        MATCH (c:OrgNode {id: $cid})
        MATCH (p:OrgNode) WHERE p.id IN $pids
        MERGE (c)-[:PART_OF]->(p)
        """,
        cid=child_id, pids=parent_ids,
    )


def link_clients(tx, node_id: str, client_ids: list[str]) -> None:
    tx.run(
        """
        MATCH (n:OrgNode {id: $nid})
        MATCH (c:Client) WHERE c.id IN $cids
        MERGE (n)-[:SERVES]->(c)
        """,
        nid=node_id, cids=client_ids,
    )


def get_node(tx, node_id: str):
    rec = tx.run(f"MATCH (n:OrgNode {{id: $id}}) RETURN {_node_map('n')} AS node", id=node_id).single()
    return rec["node"] if rec else None


def subtree(tx, root_id: str, depth: int):
    """Enumerate child->root paths up to `depth`, then assemble nested JSON in Python.
    A node with two parents under the root appears under both."""
    root = get_node(tx, root_id)
    if root is None:
        return None
    depth = int(depth)
    result = tx.run(
        f"""
        MATCH path = (n:OrgNode)-[:PART_OF*1..{depth}]->(:OrgNode {{id: $id}})
        RETURN [x IN nodes(path) | {_node_map('x')}] AS nodes
        """,
        id=root_id,
    )
    info = {root_id: root}
    children = defaultdict(set)
    for rec in result:
        ns = rec["nodes"]
        for n in ns:
            info[n["id"]] = n
        for child, parent in zip(ns, ns[1:]):
            children[parent["id"]].add(child["id"])

    def build(nid, d):
        node = {k: v for k, v in info[nid].items() if v is not None}
        kids = sorted(children[nid], key=lambda i: info[i]["name"]) if d < depth else []
        node["children"] = [build(c, d + 1) for c in kids]
        return node

    return build(root_id, 0)


# ---------- knowledge ----------
def get_knowledge_status(tx, knowledge_id: str):
    """None if missing, else {'superseded': bool}."""
    rec = tx.run(
        """
        MATCH (k:Knowledge {id: $id})
        RETURN EXISTS { (k)<-[:SUPERSEDES]-() } AS superseded
        """,
        id=knowledge_id,
    ).single()
    return None if rec is None else {"superseded": rec["superseded"]}


def get_knowledge(tx, knowledge_id: str):
    """Everything needed to build a revision; None if missing."""
    rec = tx.run(
        """
        MATCH (k:Knowledge {id: $id})
        RETURN k{.title, .summary, .keywords, .importance, .source_type, .source_uri,
                 occurred_at: toString(k.occurred_at),
                 holder_ids: [(h:OrgNode)-[:HAS_KNOWLEDGE]->(k) | h.id],
                 client_ids: [(k)-[:ABOUT]->(c:Client) | c.id],
                 superseded: EXISTS { (k)<-[:SUPERSEDES]-() }} AS k
        """,
        id=knowledge_id,
    ).single()
    return rec["k"] if rec else None


def create_knowledge(tx, props: dict, occurred_at: str, holder_ids: list[str], client_ids: list[str],
                     supersedes_id) -> None:
    tx.run(
        """
        CREATE (k:Knowledge) SET k = $props
        SET k.occurred_at = datetime($occurred_at)
        WITH k
        UNWIND $holder_ids AS hid
        MATCH (h:OrgNode {id: hid})
        MERGE (h)-[:HAS_KNOWLEDGE]->(k)
        """,
        props=props, occurred_at=occurred_at, holder_ids=holder_ids,
    )
    if client_ids:
        tx.run(
            """
            MATCH (k:Knowledge {id: $kid})
            MATCH (c:Client) WHERE c.id IN $cids
            MERGE (k)-[:ABOUT]->(c)
            """,
            kid=props["id"], cids=client_ids,
        )
    if supersedes_id:
        tx.run(
            """
            MATCH (new:Knowledge {id: $new}), (old:Knowledge {id: $old})
            CREATE (new)-[:SUPERSEDES]->(old)
            """,
            new=props["id"], old=supersedes_id,
        )


_KNOWLEDGE_ROWS = """
        WITH k, collect(DISTINCT {id: h.id, name: h.name}) AS holders
        ORDER BY k.importance DESC, k.occurred_at DESC
        RETURN k{.id, .title, .summary, .keywords, .importance, .source_type, .source_uri,
                 occurred_at: toString(k.occurred_at)} AS knowledge,
               holders,
               [(k)-[:ABOUT]->(c:Client) | {id: c.id, name: c.name}] AS clients,
               EXISTS { (k)<-[:SUPERSEDES]-() } AS superseded,
               [(k)-[:SUPERSEDES]->(o) | o.id] AS supersedes
"""


def knowledge_for_node(tx, node_id: str, recursive: bool, include_superseded: bool) -> list[dict]:
    hops = "*0.." if recursive else "*0..0"
    result = tx.run(
        f"""
        MATCH (h:OrgNode)-[:PART_OF{hops}]->(:OrgNode {{id: $id}})
        MATCH (h)-[:HAS_KNOWLEDGE]->(k:Knowledge)
        WHERE $include_superseded OR NOT EXISTS {{ (k)<-[:SUPERSEDES]-() }}
        """ + _KNOWLEDGE_ROWS,
        id=node_id, include_superseded=include_superseded,
    )
    return [r.data() for r in result]


def knowledge_about_client(tx, client_id: str, include_superseded: bool) -> list[dict]:
    """Clients hold nothing; their knowledge is whatever is linked ABOUT them."""
    result = tx.run(
        """
        MATCH (k:Knowledge)-[:ABOUT]->(:Client {id: $id})
        WHERE $include_superseded OR NOT EXISTS { (k)<-[:SUPERSEDES]-() }
        MATCH (h:OrgNode)-[:HAS_KNOWLEDGE]->(k)
        """ + _KNOWLEDGE_ROWS,
        id=client_id, include_superseded=include_superseded,
    )
    return [r.data() for r in result]


def search_candidates(tx, embedding: list[float], over_fetch: int, n_docs: int) -> list[dict]:
    """One row per (person, matching doc). Ranking (recency, keywords, ping penalty) is done
    in services.py so it stays pure and testable; this only fetches the raw signals."""
    return tx.run(
        """
        CALL db.index.vector.queryNodes('knowledge_embedding', $over_fetch, $emb)
        YIELD node AS k, score
        WHERE NOT EXISTS { (k)<-[:SUPERSEDES]-() }
        WITH k, score ORDER BY score DESC LIMIT $n_docs
        MATCH (h:OrgNode)-[:HAS_KNOWLEDGE]->(k)
        MATCH (p:Person)-[:PART_OF*0..]->(h)
        WITH DISTINCT p, k, score
        RETURN p{.id, .name, .summary, .email, .phone, user_id: p.user_id,
                 ping_count: coalesce(p.ping_count, 0)} AS person,
               k{.id, .title, .summary, .importance, .keywords,
                 occurred_at: toString(k.occurred_at)} AS doc,
               score AS similarity
        """,
        emb=embedding, over_fetch=over_fetch, n_docs=n_docs,
    ).data()


def org_paths(tx, person_ids: list[str]) -> dict[str, list]:
    """Root-to-person name paths for each person, so a suggestion shows where they sit."""
    result = tx.run(
        """
        MATCH path = (p:OrgNode)-[:PART_OF*0..]->(r:OrgNode)
        WHERE p.id IN $ids AND NOT (r)-[:PART_OF]->()
        RETURN p.id AS pid, [n IN reverse(nodes(path)) | n.name] AS path
        """,
        ids=person_ids,
    )
    by_person = defaultdict(list)
    for rec in result:
        by_person[rec["pid"]].append(rec["path"])
    return by_person


def increment_pings(tx, person_ids: list[str]) -> None:
    """Record that these people were surfaced as experts (load-balancing + management view)."""
    tx.run(
        "MATCH (p:Person) WHERE p.id IN $ids SET p.ping_count = coalesce(p.ping_count, 0) + 1",
        ids=person_ids,
    )


def ping_counts(tx) -> list[dict]:
    """All people by how often they have been surfaced. For the management dashboard."""
    return tx.run(
        """
        MATCH (p:Person)
        RETURN p{.id, .name, .email, user_id: p.user_id} AS person,
               coalesce(p.ping_count, 0) AS ping_count
        ORDER BY ping_count DESC, p.name
        """
    ).data()
