from hashlib import sha256

from holosim.frozen_idx_gate import FrozenIDXGate


def digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def test_exact_slot_match_passes():
    core = "continuity remains externally verifiable"
    gate = FrozenIDXGate(
        version=1,
        slots=(("CORE", digest(core)),),
    )

    result = gate.check(
        version=1,
        slots=(("CORE", core),),
    )

    assert result.status == "PASS"
    assert result.code == "IDX_MATCH"
    assert result.fused is False


def test_changed_slot_aborts_without_fusion():
    original = "preserve uncertainty"
    changed = "discard uncertainty"

    gate = FrozenIDXGate(
        version=1,
        slots=(("CORE", digest(original)),),
    )

    result = gate.check(
        version=1,
        slots=(("CORE", changed),),
    )

    assert result.status == "ABORT"
    assert result.code == "SLOT_HASH_MISMATCH"
    assert result.slot == "CORE"
    assert result.fused is False


def test_missing_slot_aborts():
    gate = FrozenIDXGate(
        version=1,
        slots=(
            ("CORE", digest("core")),
            ("PROTO", digest("protocol")),
        ),
    )

    result = gate.check(
        version=1,
        slots=(("CORE", "core"),),
    )

    assert result.status == "ABORT"
    assert result.code == "SLOT_MISSING"
    assert result.slot == "PROTO"
    assert result.fused is False


def test_unexpected_slot_aborts():
    gate = FrozenIDXGate(
        version=1,
        slots=(("CORE", digest("core")),),
    )

    result = gate.check(
        version=1,
        slots=(
            ("CORE", "core"),
            ("PERSONA", "unexpected"),
        ),
    )

    assert result.status == "ABORT"
    assert result.code == "SLOT_UNEXPECTED"
    assert result.slot == "PERSONA"
    assert result.fused is False


def test_slot_order_mismatch_aborts():
    gate = FrozenIDXGate(
        version=1,
        slots=(
            ("CORE", digest("core")),
            ("PROTO", digest("protocol")),
        ),
    )

    result = gate.check(
        version=1,
        slots=(
            ("PROTO", "protocol"),
            ("CORE", "core"),
        ),
    )

    assert result.status == "ABORT"
    assert result.code == "SLOT_ORDER_MISMATCH"
    assert result.fused is False


def test_version_mismatch_aborts():
    gate = FrozenIDXGate(
        version=1,
        slots=(("CORE", digest("core")),),
    )

    result = gate.check(
        version=2,
        slots=(("CORE", "core"),),
    )

    assert result.status == "ABORT"
    assert result.code == "VERSION_MISMATCH"
    assert result.fused is False