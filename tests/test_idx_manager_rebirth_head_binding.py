from hashlib import sha256

import pytest

import holosim.idx_manager as idx_manager_module
from holosim.idx_manager import IDXManager


def digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class RecordingChain:
    def __init__(self):
        self.entries = []

    def append(self, payload, *, compress):
        self.entries.append((payload, compress))


def build_manager() -> tuple[IDXManager, RecordingChain]:
    chain = RecordingChain()
    manager = IDXManager(chain=chain)
    manager.parse_spine(
        "IDX:v=1;n=1\n"
        f"S1=CORE@{digest('original')}\n"
        "ACTIVE_HASH=frozen-head\n"
    )
    return manager, chain


@pytest.mark.parametrize(
    ("rebirth_result", "expected_code"),
    [
        (
            {
                "status": "ok",
                "action": "rebirth_executed",
                "hash": "different-head",
                "fused": True,
            },
            "REBIRTH_HASH_MISMATCH",
        ),
        (
            {
                "status": "ok",
                "action": "rebirth_executed",
                "fused": True,
            },
            "REBIRTH_HASH_MISSING",
        ),
    ],
)
def test_unbound_rebirth_head_aborts_before_chain_append(
    monkeypatch,
    rebirth_result,
    expected_code,
):
    monkeypatch.setattr(
        idx_manager_module,
        "run_rebirth",
        lambda event: rebirth_result,
    )

    manager, chain = build_manager()

    result = manager.apply_to_engine(
        spine_version=1,
        spine_active_hash="frozen-head",
        slots=(("CORE", "original"),),
    )

    assert result["status"] == "abort"
    assert result["code"] == expected_code
    assert result["fused"] is False
    assert result["admission"]["code"] == "IDX_MATCH"
    assert result["rebirth_result"] == rebirth_result
    assert chain.entries == []


def test_matching_rebirth_head_allows_chain_append(monkeypatch):
    rebirth_result = {
        "status": "ok",
        "action": "rebirth_executed",
        "hash": "frozen-head",
        "fused": True,
    }
    monkeypatch.setattr(
        idx_manager_module,
        "run_rebirth",
        lambda event: rebirth_result,
    )

    manager, chain = build_manager()

    result = manager.apply_to_engine(
        spine_version=1,
        spine_active_hash="frozen-head",
        slots=(("CORE", "original"),),
    )

    assert result["status"] == "ok"
    assert result["admission"]["code"] == "IDX_MATCH"
    assert result["rebirth_result"]["hash"] == "frozen-head"
    assert len(chain.entries) == 1