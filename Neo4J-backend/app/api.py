import json
from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from . import services
from .models import CreateNodeIn, KnowledgeIn, LinkIn

bp = Blueprint("api", __name__)


def _flag(name: str, default: bool) -> bool:
    val = request.args.get(name)
    return default if val is None else val.lower() in ("1", "true", "yes")


@bp.post("/nodes")
def create_node():
    data = CreateNodeIn.model_validate(request.get_json(force=True))
    return jsonify(services.create_node(data)), 201


@bp.post("/nodes/<node_id>/parents")
def link_node(node_id):
    body = LinkIn.model_validate(request.get_json(force=True))
    return jsonify(services.link_node(node_id, body.parent_id)), 201


@bp.get("/nodes/<node_id>/subtree")
def get_subtree(node_id):
    return jsonify(services.get_subtree(node_id, request.args.get("depth", 3, type=int)))


@bp.post("/knowledge")
def add_knowledge():
    data = KnowledgeIn.model_validate(request.get_json(force=True))
    return jsonify(services.add_knowledge(data)), 201


@bp.get("/nodes/<node_id>/knowledge")
def get_knowledge_for_node(node_id):
    items = services.get_knowledge_for_node(
        node_id, recursive=_flag("recursive", True), include_superseded=_flag("include_superseded", False)
    )
    return jsonify(items)


@bp.get("/who-knows")
def who_knows():
    return jsonify(services.who_knows(request.args.get("q", "")))


@bp.errorhandler(ValidationError)
def _validation(e):
    return jsonify({"error": "validation", "details": json.loads(e.json())}), 422


@bp.errorhandler(services.ServiceError)
def _service(e):
    return jsonify({"error": str(e)}), e.status
