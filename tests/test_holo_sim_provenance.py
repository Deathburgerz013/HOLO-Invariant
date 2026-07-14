import json

from holosim.Holo_Sim import HoloSim, stable_hash


EVIDENCE_A = "a" * 64
EVIDENCE_B = "b" * 64


def structured_assertion(binding=None):
    delta = {
        "assertions": [
            {
                "claim": "camera records motion",
                "polarity": "affirmed",
                "scope": {"camera": "north"},
                "evidence_state": {"frame": 42},
            }
        ]
    }
    if binding is not None:
        delta["source_binding"] = binding
    return delta


def valid_binding():
    return {
        "source_id": "video-loop:frame-42",
        "evidence_sha256": [EVIDENCE_A, EVIDENCE_B],
    }


def test_structured_claim_without_source_binding_is_uncertain(tmp_path):
    engine = HoloSim(tmp_path / "chain.jsonl")

    result = engine.evaluate(structured_assertion())

    report = result["source_binding"]
    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert report["required"] is True
    assert report["valid"] is False
    assert report["uncertainty"][0]["kind"] == "missing_source_binding"


def test_valid_source_binding_is_hash_bound_without_claiming_truth(tmp_path):
    engine = HoloSim(tmp_path / "chain.jsonl")
    binding = valid_binding()

    result = engine.evaluate(structured_assertion(binding))

    report = result["source_binding"]
    assert result["status"] == "PASS"
    assert result["preserved"] is True
    assert report["valid"] is True
    assert report["source_id"] == binding["source_id"]
    assert report["evidence_sha256"] == binding["evidence_sha256"]
    assert report["binding_sha256"] == stable_hash(binding)
    assert "structured_source_binding" in result["verified_checks"]
    assert "do not prove" in report["interpretation_notice"]


def test_malformed_evidence_hash_is_explicit_uncertainty(tmp_path):
    engine = HoloSim(tmp_path / "chain.jsonl")
    binding = {
        "source_id": "video-loop:frame-42",
        "evidence_sha256": ["not-a-sha256"],
    }

    result = engine.evaluate(structured_assertion(binding))

    report = result["source_binding"]
    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert report["violations"] == []
    assert report["uncertainty"][0]["kind"] == "invalid_evidence_sha256"


def test_duplicate_evidence_hash_is_a_binding_violation(tmp_path):
    engine = HoloSim(tmp_path / "chain.jsonl")
    binding = {
        "source_id": "video-loop:frame-42",
        "evidence_sha256": [EVIDENCE_A, EVIDENCE_A],
    }

    result = engine.evaluate(structured_assertion(binding))

    report = result["source_binding"]
    assert result["status"] == "FLAGGED"
    assert result["preserved"] is False
    assert report["uncertainty"] == []
    assert report["violations"][0]["kind"] == "duplicate_evidence_hash"


def test_approved_commit_preserves_exact_source_binding_report(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    engine = HoloSim(chain_path)
    binding = valid_binding()

    result = engine.commit(
        structured_assertion(binding),
        reviewer="Canyon Haney",
        approval_reference="review:provenance-1",
    )

    assert result["status"] == "COMMITTED"
    assert result["accepted"] is False
    assert result["source_binding"]["binding_sha256"] == stable_hash(binding)

    entry = json.loads(chain_path.read_text(encoding="utf-8").splitlines()[0])
    payload = json.loads(entry["content"])
    assert payload["source_binding"] == result["source_binding"]
    assert payload["authority"]["accepted"] is True
