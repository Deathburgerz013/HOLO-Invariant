from holosim.Holo_Sim import HoloSim


def causal_delta(event_id, predecessors):
    return {
        "causal": {
            "event_id": event_id,
            "predecessors": predecessors,
        }
    }


def violation_kinds(result):
    return {
        violation["kind"]
        for violation in result["causal_order"]["violations"]
    }


def test_successor_may_reference_an_approved_predecessor(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    engine = HoloSim(chain_path)

    first = engine.commit(
        causal_delta("capture-1", []),
        reviewer="Canyon Haney",
        approval_reference="review:capture-1",
    )
    assert first["status"] == "COMMITTED"

    result = engine.evaluate(
        causal_delta("analysis-1", ["capture-1"])
    )

    report = result["causal_order"]
    assert result["status"] == "PASS"
    assert result["preserved"] is True
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert report["applicable"] is True
    assert report["valid"] is True
    assert report["historical_event_count"] == 1
    assert report["predecessors"] == ["capture-1"]
    assert "structured_causal_order" in result["verified_checks"]


def test_unknown_predecessor_is_flagged_without_mutation(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    engine = HoloSim(chain_path)

    result = engine.evaluate(
        causal_delta("analysis-1", ["missing-capture"])
    )

    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert result["next_state"] is None
    assert violation_kinds(result) == {"unknown_predecessor"}
    assert not chain_path.exists()


def test_self_and_duplicate_predecessor_references_are_flagged(tmp_path):
    engine = HoloSim(tmp_path / "chain.jsonl")

    result = engine.evaluate(
        causal_delta("event-1", ["event-1", "event-1"])
    )

    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert violation_kinds(result) == {
        "self_predecessor",
        "duplicate_predecessor",
    }


def test_approved_event_id_cannot_be_reused(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    engine = HoloSim(chain_path)

    committed = engine.commit(
        causal_delta("event-1", []),
        reviewer="Canyon Haney",
        approval_reference="review:event-1",
    )
    assert committed["status"] == "COMMITTED"

    result = engine.evaluate(causal_delta("event-1", []))

    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert violation_kinds(result) == {"duplicate_event_id"}


def test_malformed_causal_metadata_is_explicit_uncertainty(tmp_path):
    engine = HoloSim(tmp_path / "chain.jsonl")

    result = engine.evaluate(
        {"causal": {"event_id": "event-1"}}
    )

    report = result["causal_order"]
    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert result["violations"] == []
    assert report["violations"] == []
    assert report["uncertainty"][0]["kind"] == "invalid_predecessors"
    assert result["uncertainty"] == report["uncertainty"]
