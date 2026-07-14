import json

from holosim.Holo_Sim import HoloSim


def test_evaluate_is_read_only_and_has_no_acceptance_authority(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    engine = HoloSim(chain_path)

    result = engine.evaluate("candidate change")

    assert result["type"] == "holo_invariant_evaluation"
    assert result["version"] == "1.1"
    assert result["status"] == "PASS"
    assert result["preserved"] is True
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["uncertainty"] == []
    assert result["violations"] == []
    assert result["next_state"] is not None
    assert not chain_path.exists()


def test_evaluate_flags_invalid_contextual_factors_without_writing(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    engine = HoloSim(chain_path)

    result = engine.evaluate(
        "candidate change",
        factors={"source_strength": "unknown"},
    )

    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["next_state"] is None
    assert "All contextual factors must be numeric." in result["violations"]
    assert not chain_path.exists()


def test_commit_is_blocked_without_external_approval(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    engine = HoloSim(chain_path)

    result = engine.commit("candidate change")

    assert result["status"] == "BLOCKED"
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["commit_performed"] is False
    assert result["mutation"] is None
    assert result["authority"]["accepted"] is False
    assert result["authority"]["source"] == "external_human_required"
    assert not chain_path.exists()


def test_commit_records_separate_external_authority(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    engine = HoloSim(chain_path)

    result = engine.commit(
        "candidate change",
        reviewer="Canyon Haney",
        approval_reference="review:test-approval-1",
    )

    assert result["status"] == "COMMITTED"
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["commit_performed"] is True
    assert result["authority"] == {
        "accepted": True,
        "source": "external_human",
        "reviewer": "Canyon Haney",
        "approval_reference": "review:test-approval-1",
    }
    assert result["mutation"] is not None

    lines = chain_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    chain_entry = json.loads(lines[0])
    committed_payload = json.loads(chain_entry["content"])
    assert committed_payload["authority"] == result["authority"]
    assert committed_payload["type"] == "holo_sim_commit"
