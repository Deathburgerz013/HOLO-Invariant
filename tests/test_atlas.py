from holosim.atlas import build_atlas, validate_atlas


def test_atlas_binds_typed_relationship_across_domains():
    nodes = [
        {
            "domain": "receipt_graph",
            "object_type": "receipt",
            "object_id": "receipt:analysis-1",
            "object_hash": "a" * 64,
        },
        {
            "domain": "continuity_topology",
            "object_type": "record",
            "object_id": "chain:record-7",
            "object_hash": "b" * 64,
        },
    ]

    edges = [
        {
            "source_node_id": "receipt:analysis-1",
            "relation": "JUSTIFIES",
            "target_node_id": "chain:record-7",
            "evidence_refs": ["a" * 64],
            "scope": "test",
            "status": "DECLARED",
        }
    ]

    atlas = build_atlas(nodes=nodes, edges=edges)

    assert atlas["type"] == "holo_atlas"
    assert atlas["version"] == 1
    assert atlas["nodes"] == nodes
    assert atlas["edges"] == edges

    assert atlas["truth_claimed"] is False
    assert atlas["accepted"] is False
    assert atlas["write_authority"] == "NONE"
    assert atlas["execution_authority"] == "NONE"

    assert isinstance(atlas["atlas_hash"], str)
    assert len(atlas["atlas_hash"]) == 64

    assert validate_atlas(atlas) is True
def test_atlas_rejects_edge_with_unknown_endpoint():
    import pytest

    from holosim.atlas import AtlasError

    nodes = [
        {
            "domain": "receipt_graph",
            "object_type": "receipt",
            "object_id": "receipt:analysis-1",
            "object_hash": "a" * 64,
        }
    ]

    edges = [
        {
            "source_node_id": "receipt:analysis-1",
            "relation": "JUSTIFIES",
            "target_node_id": "missing:node",
            "evidence_refs": ["a" * 64],
            "scope": "test",
            "status": "DECLARED",
        }
    ]

    with pytest.raises(
        AtlasError,
        match="edge references unknown target node",
    ):
        build_atlas(nodes=nodes, edges=edges)
def test_atlas_rejects_undeclared_relationship_type():
    import pytest

    from holosim.atlas import AtlasError

    nodes = [
        {
            "domain": "receipt_graph",
            "object_type": "receipt",
            "object_id": "receipt:analysis-1",
            "object_hash": "a" * 64,
        },
        {
            "domain": "continuity_topology",
            "object_type": "record",
            "object_id": "chain:record-7",
            "object_hash": "b" * 64,
        },
    ]

    edges = [
        {
            "source_node_id": "receipt:analysis-1",
            "relation": "MAGICALLY_PROVES",
            "target_node_id": "chain:record-7",
            "evidence_refs": ["a" * 64],
            "scope": "test",
            "status": "DECLARED",
        }
    ]

    with pytest.raises(
        AtlasError,
        match="edge relation is not declared by this version",
    ):
        build_atlas(nodes=nodes, edges=edges)
def test_atlas_rejects_malformed_node_hash():
    import pytest

    from holosim.atlas import AtlasError

    nodes = [
        {
            "domain": "receipt_graph",
            "object_type": "receipt",
            "object_id": "receipt:analysis-1",
            "object_hash": "definitely-not-a-sha256",
        }
    ]

    with pytest.raises(
        AtlasError,
        match="node.object_hash must be a lowercase SHA-256 hash",
    ):
        build_atlas(nodes=nodes, edges=[])
def test_atlas_rejects_duplicate_node_identity():
    import pytest

    from holosim.atlas import AtlasError

    nodes = [
        {
            "domain": "receipt_graph",
            "object_type": "receipt",
            "object_id": "shared:object-1",
            "object_hash": "a" * 64,
        },
        {
            "domain": "continuity_topology",
            "object_type": "record",
            "object_id": "shared:object-1",
            "object_hash": "b" * 64,
        },
    ]

    with pytest.raises(
        AtlasError,
        match="node object_id values must be unique",
    ):
        build_atlas(nodes=nodes, edges=[])
