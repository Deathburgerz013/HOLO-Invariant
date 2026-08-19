"""Verified read-only projection of HoloChain relationships."""

from pathlib import Path
from typing import Any

from holosim.config import DEFAULT_CHAIN_FILE
from holosim.core import HoloChain


def build_continuity_topology(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
) -> dict[str, Any]:
    """Return verified records plus their explicit continuity relations."""
    chain = HoloChain(chain_path)
    entries, decoded, _, _ = chain._revalidation_view()
    if len(entries) != len(decoded):
        raise ValueError("Verified topology projection is incomplete")

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for position, (entry, content) in enumerate(zip(entries, decoded)):
        record_type = content.get("_holo_record_type") if isinstance(content, dict) else None
        kind = {
            "holo_correction": "correction",
            "holo_revalidation": "revalidation",
        }.get(record_type, "record")
        node = {
            "idx": entry["idx"],
            "kind": kind,
            "timestamp": entry.get("timestamp"),
            "hash": entry["hash"],
            "prev_hash": entry.get("prev_hash"),
            "content": content,
        }
        if kind in {"correction", "revalidation"}:
            node["target_idx"] = content["target_idx"] if kind == "revalidation" else content["corrects_idx"]
            node["target_hash"] = content["target_hash"] if kind == "revalidation" else content["corrects_hash"]
        if kind == "revalidation":
            node["outcome"] = content["outcome"]
        nodes.append(node)

        if position:
            edges.append({
                "kind": "continuity",
                "source": entries[position - 1]["idx"],
                "target": entry["idx"],
            })

    for node in nodes:
        if node["kind"] == "correction":
            edges.append({
                "kind": "correction",
                "source": node["target_idx"],
                "target": node["idx"],
            })
        elif node["kind"] == "revalidation":
            edges.append({
                "kind": "revalidation",
                "source": node["target_idx"],
                "target": node["idx"],
                "outcome": node["outcome"],
            })

    return {
        "type": "holo_continuity_topology",
        "version": 1,
        "verified": True,
        "source_entries": len(entries),
        "nodes": nodes,
        "edges": edges,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
