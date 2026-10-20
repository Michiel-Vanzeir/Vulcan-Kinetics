import uuid
from . import hierarchy
from . import config, repository as repo
from .db import get_driver
from .embedding import embed, build_knowledge_text
from .models import CreateNodeIn, KnowledgeIn


class ServiceError(Exception):
    status = 400


class NotFound(ServiceError):
    status = 404


class Invalid(ServiceError):
    status = 422


class Conflict(ServiceError):
    status = 409


def _check_parents(child_type: str, parent_ids: list[str], types: dict) -> None:
    allowed = hierarchy.ALLOWED_PARENTS[child_type]
    for pid in parent_ids:
        ptype = types.get(pid)
        if ptype is None:
            raise NotFound(f"Parent node {pid} not found")
        if ptype not in allowed:
            allowed_txt = ", ".join(sorted(allowed)) or "none (Departments are roots)"
            raise Invalid(f"A {child_type} cannot be under a {ptype}. Allowed parents: {allowed_txt}")


# ---------- org ----------
def create_node(data: CreateNodeIn) -> dict:
    node_id = str(uuid.uuid4())
    props = {"id": node_id, "name": data.name, "summary": data.summary}
    if data.type == "Person":
        props.update({k: v for k, v in (("email", data.email), ("phone", data.phone)) if v})

    def work(tx):
        _check_parents(data.type, data.parent_ids, repo.get_types(tx, data.parent_ids))
        repo.create_node(tx, data.type, props)
        if data.parent_ids:
            repo.link(tx, node_id, data.parent_ids)

    with get_driver().session() as s:
        s.execute_write(work)
    return {**props, "type": data.type, "parent_ids": data.parent_ids}


def link_node(child_id: str, parent_id: str) -> dict:
    def work(tx):
        types = repo.get_types(tx, [child_id, parent_id])
        if child_id not in types:
            raise NotFound(f"Node {child_id} not found")
        _check_parents(types[child_id], [parent_id], types)
        repo.link(tx, child_id, [parent_id])  # MERGE: duplicate edges are a no-op

    with get_driver().session() as s:
        s.execute_write(work)
    return {"child_id": child_id, "parent_id": parent_id}


def get_subtree(node_id: str, depth: int = 3) -> dict:
    if not 1 <= depth <= 10:
        raise Invalid("depth must be between 1 and 10")
    with get_driver().session() as s:
        tree = s.execute_read(repo.subtree, node_id, depth)
    if tree is None:
        raise NotFound(f"Node {node_id} not found")
    return tree


# ---------- knowledge ----------
def add_knowledge(data: KnowledgeIn) -> dict:
    """Creates the Knowledge node (embedding built here from title + summary + keywords),
    attaches it to the holders and, optionally, supersedes an older item, all in one transaction."""
    embedding = embed(build_knowledge_text(data.title, data.summary, data.keywords))  # slow; outside tx
    k_id = str(uuid.uuid4())
    props = {
        "id": k_id, "title": data.title, "summary": data.summary, "keywords": data.keywords,
        "importance": data.importance, "source_type": data.source_type,
        "source_uri": data.source_uri, "embedding": embedding,
    }
    holder_ids = list(dict.fromkeys(data.holder_ids))

    def work(tx):
        types = repo.get_types(tx, holder_ids)
        missing = [h for h in holder_ids if h not in types]
        if missing:
            raise NotFound(f"Holder node(s) not found: {missing}")
        if data.supersedes_id:
            status = repo.get_knowledge_status(tx, data.supersedes_id)
            if status is None:
                raise NotFound(f"Knowledge {data.supersedes_id} not found")
            if status["superseded"]:
                raise Conflict(f"Knowledge {data.supersedes_id} is already superseded")
        repo.create_knowledge(tx, props, data.occurred_at.isoformat(), holder_ids, data.supersedes_id)

    with get_driver().session() as s:
        s.execute_write(work)
    return {k: v for k, v in props.items() if k != "embedding"} | {
        "occurred_at": data.occurred_at.isoformat(),
        "holder_ids": holder_ids,
        "supersedes_id": data.supersedes_id,
    }


def get_knowledge_for_node(node_id: str, recursive: bool = True, include_superseded: bool = False) -> list[dict]:
    with get_driver().session() as s:
        if s.execute_read(repo.get_node, node_id) is None:
            raise NotFound(f"Node {node_id} not found")
        return s.execute_read(repo.knowledge_for_node, node_id, recursive, include_superseded)


# ---------- search ----------
def who_knows(query: str) -> list[dict]:
    if not query.strip():
        raise Invalid("Query must not be empty")
    emb = embed(query)
    with get_driver().session() as s:
        return s.execute_read(
            repo.who_knows, emb, config.VECTOR_OVER_FETCH,
            config.WHO_KNOWS_DOCS, config.WHO_KNOWS_PEOPLE,
        )
