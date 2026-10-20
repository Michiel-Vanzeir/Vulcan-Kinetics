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


def create_knowledge(tx, props: dict, occurred_at: str, holder_ids: list[str], supersedes_id) -> None:
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
    if supersedes_id:
        tx.run(
            """
            MATCH (new:Knowledge {id: $new}), (old:Knowledge {id: $old})
            CREATE (new)-[:SUPERSEDES]->(old)
            """,
            new=props["id"], old=supersedes_id,
        )


def knowledge_for_node(tx, node_id: str, recursive: bool, include_superseded: bool) -> list[dict]:
    hops = "*0.." if recursive else "*0..0"
    result = tx.run(
        f"""
        MATCH (h:OrgNode)-[:PART_OF{hops}]->(:OrgNode {{id: $id}})
        MATCH (h)-[:HAS_KNOWLEDGE]->(k:Knowledge)
        WHERE $include_superseded OR NOT EXISTS {{ (k)<-[:SUPERSEDES]-() }}
        WITH k, collect(DISTINCT {{id: h.id, name: h.name}}) AS holders
        ORDER BY k.importance DESC, k.occurred_at DESC
        RETURN k{{.id, .title, .summary, .keywords, .importance, .source_type, .source_uri,
                 occurred_at: toString(k.occurred_at)}} AS knowledge,
               holders,
               EXISTS {{ (k)<-[:SUPERSEDES]-() }} AS superseded,
               [(k)-[:SUPERSEDES]->(o) | o.id] AS supersedes
        """,
        id=node_id, include_superseded=include_superseded,
    )
    return [r.data() for r in result]


def who_knows(tx, embedding: list[float], over_fetch: int, n_docs: int, n_people: int) -> list[dict]:
    rows = tx.run(
        """
        CALL db.index.vector.queryNodes('knowledge_embedding', $over_fetch, $emb)
        YIELD node AS k, score
        WHERE NOT EXISTS { (k)<-[:SUPERSEDES]-() }
        WITH k, score ORDER BY score DESC LIMIT $n_docs
        MATCH (h:OrgNode)-[:HAS_KNOWLEDGE]->(k)
        MATCH (p:Person)-[:PART_OF*0..]->(h)
        WITH DISTINCT p, k, score
        RETURN p{.id, .name, .summary, .email, .phone} AS person,
               sum(score) AS score,
               max(k.importance) AS max_importance,
               collect({id: k.id, title: k.title, summary: k.summary,
                        importance: k.importance, similarity: score}) AS docs
        ORDER BY score DESC, max_importance DESC
        LIMIT $n_people
        """,
        emb=embedding, over_fetch=over_fetch, n_docs=n_docs, n_people=n_people,
    ).data()
    if not rows:
        return []
    paths = tx.run(
        """
        MATCH path = (p:OrgNode)-[:PART_OF*0..]->(r:OrgNode)
        WHERE p.id IN $ids AND NOT (r)-[:PART_OF]->()
        RETURN p.id AS pid, [n IN reverse(nodes(path)) | n.name] AS path
        """,
        ids=[r["person"]["id"] for r in rows],
    )
    by_person = defaultdict(list)
    for rec in paths:
        by_person[rec["pid"]].append(rec["path"])
    for r in rows:
        r["org_paths"] = by_person[r["person"]["id"]]
    return rows
