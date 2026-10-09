import pytest

from holosim.core import HoloChain
from holosim.continuity_checkpoint import (
    build_continuity_checkpoint,
    verify_continuity_checkpoint,
    verify_continuity_checkpoint_against_chain,
)


def test_independent_observer_verifies_same_source(tmp_path):
    path = tmp_path / "memory.jsonl"

    observer_a = HoloChain(path)
    original = observer_a.append({"claim": "Initial observation"})
    observer_a.correct(
        original["idx"],
        {"claim": "Corrected observation"},
        reason="New evidence",
    )
    checkpoint = build_continuity_checkpoint(observer_a)

    observer_b = HoloChain(path)
    result = verify_continuity_checkpoint_against_chain(
        checkpoint, observer_b
    )

    assert result["valid"] is True


def test_internally_valid_checkpoint_rejected_against_wrong_source(tmp_path):
    source_a = HoloChain(tmp_path / "source_a.jsonl")
    source_a.append({"claim": "A"})
    checkpoint_a = build_continuity_checkpoint(source_a)

    source_b = HoloChain(tmp_path / "source_b.jsonl")
    source_b.append({"claim": "B"})

    assert verify_continuity_checkpoint(checkpoint_a)["valid"] is True

    with pytest.raises(ValueError):
        verify_continuity_checkpoint_against_chain(
            checkpoint_a, source_b
        )


def test_missing_source_cannot_verify_checkpoint(tmp_path):
    source = HoloChain(tmp_path / "existing.jsonl")
    source.append({"claim": "Recorded evidence"})
    checkpoint = build_continuity_checkpoint(source)

    missing_source = HoloChain(tmp_path / "missing.jsonl")

    with pytest.raises(ValueError):
        verify_continuity_checkpoint_against_chain(
            checkpoint, missing_source
        )
