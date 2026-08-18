from hashlib import sha256

from holosim.frozen_idx_gate import FrozenIDXGate


def digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def build_gate() -> FrozenIDXGate:
    return FrozenIDXGate(
        version=1,
        active_hash="frozen-head",
        slots=(("CORE", digest("original")),),
    )


def test_wrong_active_hash_aborts_before_slot_admission():
    gate = build_gate()

    result = gate.check(
        version=1,
        active_hash="moving-head",
        slots=(("CORE", "original"),),
    )

    assert result.status == "ABORT"
    assert result.code == "ACTIVE_HASH_MISMATCH"
    assert result.expected == "frozen-head"
    assert result.observed == "moving-head"
    assert result.fused is False


def test_exact_active_hash_allows_matching_slots():
    gate = build_gate()

    result = gate.check(
        version=1,
        active_hash="frozen-head",
        slots=(("CORE", "original"),),
    )

    assert result.status == "PASS"
    assert result.code == "IDX_MATCH"


def test_frozen_active_hash_is_exposed_read_only():
    gate = build_gate()

    assert gate.active_hash == "frozen-head"