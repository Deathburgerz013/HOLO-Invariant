from holosim.Holo_Sim import HoloSim


EVIDENCE_SHA256 = "a" * 64


def source_binding():
    return {
        "source_id": "video-loop:test-fixture",
        "evidence_sha256": [EVIDENCE_SHA256],
    }


def assertion(
    polarity,
    *,
    claim="camera records motion",
    scope=None,
    evidence_state=None,
):
    return {
        "claim": claim,
        "polarity": polarity,
        "scope": scope or {"camera": "north"},
        "evidence_state": evidence_state or {"frame": 42},
    }


def test_matching_claim_scope_and_evidence_with_opposite_polarity_is_flagged(
    tmp_path,
):
    engine = HoloSim(tmp_path / "chain.jsonl")

    result = engine.evaluate(
        {
            "source_binding": source_binding(),
            "assertions": [
                assertion("affirmed"),
                assertion("negated"),
            ]
        }
    )

    report = result["non_contradiction"]
    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert report["valid"] is False
    assert report["checked_assertion_count"] == 2
    assert report["contradiction_count"] == 1
    assert report["uncertainty"] == []
    assert result["next_state"] is None


def test_opposite_polarity_under_different_scope_is_not_a_contradiction(tmp_path):
    engine = HoloSim(tmp_path / "chain.jsonl")

    result = engine.evaluate(
        {
            "source_binding": source_binding(),
            "assertions": [
                assertion("affirmed", scope={"camera": "north"}),
                assertion("negated", scope={"camera": "south"}),
            ]
        }
    )

    report = result["non_contradiction"]
    assert result["status"] == "PASS"
    assert result["preserved"] is True
    assert report["valid"] is True
    assert report["contradiction_count"] == 0
    assert "structured_non_contradiction" in result["verified_checks"]


def test_incomplete_assertion_is_preserved_as_uncertainty_and_blocks_result(
    tmp_path,
):
    engine = HoloSim(tmp_path / "chain.jsonl")

    result = engine.evaluate(
        {
            "source_binding": source_binding(),
            "assertions": [
                {
                    "claim": "camera records motion",
                    "polarity": "affirmed",
                }
            ]
        }
    )

    report = result["non_contradiction"]
    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert result["violations"] == []
    assert result["uncertainty"] == report["uncertainty"]
    assert report["contradiction_count"] == 0
    assert report["uncertainty"][0]["kind"] == "invalid_assertion"
    assert set(report["uncertainty"][0]["missing_fields"]) == {
        "scope",
        "evidence_state",
    }


def test_incoming_assertion_is_checked_against_approved_history(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    engine = HoloSim(chain_path)

    committed = engine.commit(
        {
            "source_binding": source_binding(),
            "assertions": [assertion("affirmed")],
        },
        reviewer="Canyon Haney",
        approval_reference="review:assertion-1",
    )
    assert committed["status"] == "COMMITTED"

    result = engine.evaluate(
        {
            "source_binding": source_binding(),
            "assertions": [assertion("negated")],
        }
    )

    report = result["non_contradiction"]
    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert report["historical_assertion_count"] == 1
    assert report["incoming_assertion_count"] == 1
    assert report["contradiction_count"] == 1
    contradiction = report["contradictions"][0]
    assert contradiction["affirmed"][0]["origin"] == "committed"
    assert contradiction["negated"][0]["origin"] == "incoming"
