import json
import threading
from urllib.request import urlopen

from holosim.core import HoloChain
from holosim.operator_console import (
    TOPOLOGY_HTML,
    _OperatorServer,
    build_continuity_topology,
)


def _read(url: str) -> tuple[int, str, bytes]:
    with urlopen(url, timeout=3) as response:
        return (
            response.status,
            response.headers["Content-Type"],
            response.read(),
        )


def build_relational_chain(path):
    chain = HoloChain(path)
    original = chain.append({"claim": "original"})
    correction = chain.correct(
        original["idx"],
        {"claim": "corrected"},
        "new evidence",
    )
    revalidation = chain.revalidate(
        original["idx"],
        "HELD",
        "source still matches",
        "manual comparison",
    )
    return chain, original, correction, revalidation


def test_topology_projects_only_verified_relations(tmp_path):
    chain_path = tmp_path / "topology.jsonl"
    _, original, correction, revalidation = build_relational_chain(
        chain_path
    )

    topology = build_continuity_topology(chain_path)

    assert topology["type"] == "holo_continuity_topology"
    assert topology["version"] == 1
    assert topology["verified"] is True
    assert topology["source_entries"] == 3
    assert [node["kind"] for node in topology["nodes"]] == [
        "record",
        "correction",
        "revalidation",
    ]
    assert topology["nodes"][0]["content"] == {
        "claim": "original"
    }
    assert topology["nodes"][1]["target_idx"] == original["idx"]
    assert topology["nodes"][1]["target_hash"] == original["hash"]
    assert topology["nodes"][2]["target_idx"] == original["idx"]
    assert topology["nodes"][2]["target_hash"] == original["hash"]

    assert topology["edges"] == [
        {
            "kind": "continuity",
            "source": original["idx"],
            "target": correction["idx"],
        },
        {
            "kind": "continuity",
            "source": correction["idx"],
            "target": revalidation["idx"],
        },
        {
            "kind": "correction",
            "source": original["idx"],
            "target": correction["idx"],
        },
        {
            "kind": "revalidation",
            "source": original["idx"],
            "target": revalidation["idx"],
            "outcome": "HELD",
        },
    ]
    assert topology["accepted"] is False
    assert topology["truth_claimed"] is False
    assert topology["write_authority"] == "NONE"
    assert topology["execution_authority"] == "NONE"


def test_empty_verified_chain_has_empty_topology(tmp_path):
    topology = build_continuity_topology(tmp_path / "empty.jsonl")

    assert topology["verified"] is True
    assert topology["source_entries"] == 0
    assert topology["nodes"] == []
    assert topology["edges"] == []


def test_topology_page_exposes_real_graph_controls():
    assert "HOLO / CONTINUITY TOPOLOGY" in TOPOLOGY_HTML
    assert "VERIFIED RECORD GRAPH" in TOPOLOGY_HTML
    assert 'id="topologyGraph"' in TOPOLOGY_HTML
    assert 'id="nodeReceipt"' in TOPOLOGY_HTML
    assert "CONTINUITY" in TOPOLOGY_HTML
    assert "CORRECTION" in TOPOLOGY_HTML
    assert "REVALIDATION" in TOPOLOGY_HTML
    assert "OBSERVATIONAL ONLY" in TOPOLOGY_HTML


def test_topology_routes_are_read_only(tmp_path):
    chain_path = tmp_path / "topology.jsonl"
    build_relational_chain(chain_path)
    before = chain_path.read_bytes()

    server = _OperatorServer(("127.0.0.1", 0), chain_path)
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()

    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        page_status, page_type, page = _read(base + "/topology")
        api_status, api_type, api_body = _read(base + "/api/topology")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    topology = json.loads(api_body)
    assert page_status == 200
    assert page_type.startswith("text/html")
    assert b"HOLO / CONTINUITY TOPOLOGY" in page
    assert api_status == 200
    assert api_type.startswith("application/json")
    assert topology["verified"] is True
    assert topology["source_entries"] == 3
    assert chain_path.read_bytes() == before
