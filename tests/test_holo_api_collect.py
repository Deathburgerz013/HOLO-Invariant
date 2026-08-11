from holosim.api import HoloAPI


def test_collect_without_external_approval_blocks_cleanly(tmp_path):
    api = HoloAPI(tmp_path / "chain.jsonl")

    result = api.collect("actual user content")

    assert result["status"] == "blocked"
    assert result["result"]["reason"] == "external_approval_required"
    assert result["result"]["append"]["commit_performed"] is False


def test_collect_forwards_external_approval_and_verifies_append(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    api = HoloAPI(chain_path)

    result = api.collect(
        "actual user content",
        reviewer="external-reviewer",
        approval_reference="approval-001",
    )

    assert result["status"] == "collected"
    assert result["result"]["append"]["commit_performed"] is True
    assert result["result"]["append"]["authority"] == {
        "accepted": True,
        "source": "external_human",
        "reviewer": "external-reviewer",
        "approval_reference": "approval-001",
    }
    assert result["result"]["verify"]["status"] == "ok"
    assert result["result"]["verify"]["entries"] == 1
    assert chain_path.exists()
