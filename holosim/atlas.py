"""Deterministic cross-domain Atlas relationships.

Atlas binds typed relationships between independently verified HOLO objects
without granting truth, acceptance, write authority, or execution authority.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash


ATLAS_TYPE = "holo_atlas"
VERSION = 1

RELATIONS = {
    "DEPENDS_ON",
    "JUSTIFIES",
    "VERIFIED_BY",
    "CORRECTS",
    "DERIVED_FROM",
    "REQUIRES",
    "REFERENCES",
    "OBSERVED_IN",
    "SUPERSEDES",
}

NODE_FIELDS = {
    "domain",
    "object_type",
    "object_id",
    "object_hash",
}

EDGE_FIELDS = {
    "source_node_id",
    "relation",
    "target_node_id",
    "evidence_refs",
    "scope",
    "status",
}

ATLAS_FIELDS = {
    "type",
    "version",
    "nodes",
    "edges",
    "truth_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "interpretation_notice",
    "atlas_hash",
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

NOTICE = (
    "Atlas records declared cross-domain relationships only. "
    "It does not establish truth, acceptance, provenance independence, "
    "write authority, execution authority, or permission to act."
)


class AtlasError(ValueError):
    """Raised when Atlas structure or relationships fail validation."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise AtlasError(f"{field} must be a nonempty plain string")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise AtlasError(f"{field} must be valid UTF-8") from exc
    return value


def _sha256(value: Any, field: str) -> str:
    text = _text(value, field)
    if _SHA256_RE.fullmatch(text) is None:
        raise AtlasError(f"{field} must be a lowercase SHA-256 hash")
    return text


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise AtlasError(str(exc)) from exc


def _normalize_node(value: Mapping[str, Any]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != NODE_FIELDS:
        raise AtlasError("node fields do not match the versioned schema")

    return {
        "domain": _text(value["domain"], "node.domain"),
        "object_type": _text(value["object_type"], "node.object_type"),
        "object_id": _text(value["object_id"], "node.object_id"),
        "object_hash": _sha256(value["object_hash"], "node.object_hash"),
    }


def _normalize_evidence_refs(value: Any) -> list[str]:
    if type(value) not in {list, tuple}:
        raise AtlasError("edge.evidence_refs must be a list or tuple")

    refs = [
        _sha256(item, "edge.evidence_refs item")
        for item in value
    ]

    if len(refs) != len(set(refs)):
        raise AtlasError("edge.evidence_refs must be unique")

    return refs


def _normalize_edge(
    value: Mapping[str, Any],
    *,
    node_ids: set[str],
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != EDGE_FIELDS:
        raise AtlasError("edge fields do not match the versioned schema")

    source = _text(value["source_node_id"], "edge.source_node_id")
    target = _text(value["target_node_id"], "edge.target_node_id")
    relation = _text(value["relation"], "edge.relation")

    if source not in node_ids:
        raise AtlasError("edge references unknown source node")
    if target not in node_ids:
        raise AtlasError("edge references unknown target node")
    if relation not in RELATIONS:
        raise AtlasError("edge relation is not declared by this version")

    return {
        "source_node_id": source,
        "relation": relation,
        "target_node_id": target,
        "evidence_refs": _normalize_evidence_refs(value["evidence_refs"]),
        "scope": _text(value["scope"], "edge.scope"),
        "status": _text(value["status"], "edge.status"),
    }


def _body(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "type": ATLAS_TYPE,
        "version": VERSION,
        "nodes": deepcopy(nodes),
        "edges": deepcopy(edges),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": NOTICE,
    }


def build_atlas(
    *,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one deterministic cross-domain relation graph."""

    if type(nodes) not in {list, tuple}:
        raise AtlasError("nodes must be a list or tuple")
    if type(edges) not in {list, tuple}:
        raise AtlasError("edges must be a list or tuple")

    normalized_nodes = [_normalize_node(node) for node in nodes]

    node_ids = [node["object_id"] for node in normalized_nodes]
    if len(node_ids) != len(set(node_ids)):
        raise AtlasError("node object_id values must be unique")

    node_id_set = set(node_ids)

    normalized_edges = [
        _normalize_edge(edge, node_ids=node_id_set)
        for edge in edges
    ]

    edge_keys = [
        (
            edge["source_node_id"],
            edge["relation"],
            edge["target_node_id"],
            tuple(edge["evidence_refs"]),
            edge["scope"],
            edge["status"],
        )
        for edge in normalized_edges
    ]
    if len(edge_keys) != len(set(edge_keys)):
        raise AtlasError("atlas edges must be unique")

    body = _body(
        nodes=normalized_nodes,
        edges=normalized_edges,
    )

    return {
        **body,
        "atlas_hash": _hash(body),
    }


def validate_atlas(atlas: Mapping[str, Any]) -> bool:
    """Rebuild an Atlas and require exact schema, identity, and relationships."""

    if type(atlas) is not dict:
        raise AtlasError("atlas must be a plain dictionary")
    if set(atlas) != ATLAS_FIELDS:
        raise AtlasError("atlas fields do not match the versioned schema")

    if atlas.get("type") != ATLAS_TYPE or atlas.get("version") != VERSION:
        raise AtlasError("atlas type or version is invalid")

    if atlas.get("truth_claimed") is not False:
        raise AtlasError("atlas cannot claim truth")
    if atlas.get("accepted") is not False:
        raise AtlasError("atlas cannot grant acceptance")
    if atlas.get("write_authority") != "NONE":
        raise AtlasError("atlas cannot grant write authority")
    if atlas.get("execution_authority") != "NONE":
        raise AtlasError("atlas cannot grant execution authority")
    if atlas.get("interpretation_notice") != NOTICE:
        raise AtlasError("atlas interpretation_notice is invalid")

    rebuilt = build_atlas(
        nodes=atlas["nodes"],
        edges=atlas["edges"],
    )

    if rebuilt != atlas:
        raise AtlasError(
            "atlas does not match deterministic reconstruction"
        )

    return True
