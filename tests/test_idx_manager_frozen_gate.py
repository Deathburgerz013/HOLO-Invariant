from hashlib import sha256

import holosim.idx_manager as idx_manager_module
from holosim.idx_manager import IDXManager


def digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class RecordingChain:
    def __init__(self):
        self.entries = []

    def append(self, payload, *, compress):
        self.entries.append((payload, compress))


def build_manager(
    expected_text: str,
) -> tuple[IDXManager, RecordingChain]:
    chain = RecordingChain()
    manager = IDXManager(chain=chain)
    manager.parse_spine(
        "IDX:v=1;n=1\n"
        f"S1=CORE@{digest(expected_text)}\n"
        "ACTIVE_HASH=frozen-head\n"
    )
    return manager, chain


def test_mismatch_aborts_before_rebirth_or_chain_append(monkeypatch):
    rebirth_calls = []

    def fake_rebirth(event):
        rebirth_calls.append(event)
        return {"status": "ok", "action": "rebirth_executed"}

    monkeypatch.setattr(
        idx_manager_module,
        "run_rebirth",
        fake_rebirth,
    )

    manager, chain = build_manager("original")

    result = manager.apply_to_engine(
        spine_version=1,
        spine_active_hash="frozen-head",
        slots=(("CORE", "changed"),),
    )

    assert result["status"] == "abort"
    assert result["code"] == "SLOT_HASH_MISMATCH"
    assert rebirth_calls == []
    assert chain.entries == []


def test_exact_match_allows_rebirth_and_chain_append(monkeypatch):
    rebirth_calls = []

    def fake_rebirth(event):
        rebirth_calls.append(event)
        return {
            "status": "ok",
            "action": "rebirth_executed",
            "fused": True,
        }

    monkeypatch.setattr(
        idx_manager_module,
        "run_rebirth",
        fake_rebirth,
    )

    manager, chain = build_manager("original")

    result = manager.apply_to_engine(
        spine_version=1,
        spine_active_hash="frozen-head",
        slots=(("CORE", "original"),),
    )

    assert result["status"] == "ok"
    assert result["admission"]["code"] == "IDX_MATCH"
    assert rebirth_calls == ["MANUAL_OVERRIDE"]
    assert len(chain.entries) == 1
