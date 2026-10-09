import pytest

from holosim.core import HoloChain


def test_service_append_cannot_be_corrected_as_claim(tmp_path):
    chain = HoloChain(tmp_path / "operational.jsonl")

    operational = chain.append({
        "type": "service_append",
        "source": "HoloService",
        "content": "Operational event",
    })

    with pytest.raises(ValueError):
        chain.correct(
            operational["idx"],
            {"claim": "Replacement"},
            "Operational records are not original claims",
        )


def test_service_append_cannot_be_revalidated_as_claim(tmp_path):
    chain = HoloChain(tmp_path / "revalidation.jsonl")

    operational = chain.append({
        "type": "service_append",
        "source": "HoloService",
        "content": "Operational event",
    })

    with pytest.raises(ValueError):
        chain.revalidate(
            operational["idx"],
            "HELD",
            "Test evidence",
            "Test method",
        )


def test_stored_correction_cannot_target_service_append(tmp_path):
    chain = HoloChain(tmp_path / "stored_correction.jsonl")

    operational = chain.append({
        "type": "service_append",
        "source": "HoloService",
        "content": "Operational event",
    })

    chain.append({
        "_holo_record_type": "holo_correction",
        "version": 1,
        "corrects_idx": operational["idx"],
        "corrects_hash": operational["hash"],
        "reason": "Attempted operational correction",
        "replacement": {"claim": "Replacement"},
    })

    with pytest.raises(ValueError):
        chain.get_effective_state()


def test_stored_revalidation_cannot_target_service_append(tmp_path):
    chain = HoloChain(tmp_path / "stored_revalidation.jsonl")

    operational = chain.append({
        "type": "service_append",
        "source": "HoloService",
        "content": "Operational event",
    })

    chain.append({
        "_holo_record_type": "holo_revalidation",
        "version": 1,
        "target_idx": operational["idx"],
        "target_hash": operational["hash"],
        "subject_hash": chain._content_digest({
            "type": "service_append",
            "source": "HoloService",
            "content": "Operational event",
        }),
        "subject_correction_idx": None,
        "outcome": "HELD",
        "method": "Test method",
        "evidence": "Test evidence",
    })

    with pytest.raises(ValueError):
        chain.get_claim_index()
