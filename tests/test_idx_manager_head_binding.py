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


def build_manager() -> tuple[IDXManager, RecordingChain]:
    chain = RecordingChain()
    manager = IDXManager(chain=chain)
    manager.parse_spine(
        "IDX:v=1;n=1\n"
        f"S1=CORE@{digest('original')}\n"
        "ACTIVE_HASH=frozen-head\n"
    )
    return manager, chain


def test_wrong_loaded_idx_head_aborts_before_rebirth_or_append(
    monkeypatch,
):
    rebirth_calls = []

    def fake_rebirth(event):
        rebirth_calls.append(event)
        return {"status": "ok"}

    monkeypatch.setattr(
        idx_manager_module,
        "run_rebirth",
        fake_rebirth,
    )

    manager, chain = build_manager()

    result = manager.apply_to_engine(
        spine_version=1,
        spine_active_hash="moving-head",
        slots=(("CORE", "original"),),
    )

    assert result["status"] == "abort"
    assert result["code"] == "ACTIVE_HASH_MISMATCH"
    assert result["admission"]["expected"] == "frozen-head"
    assert result["admission"]["observed"] == "moving-head"
    assert rebirth_calls == []
    assert chain.entries == []


def test_exact_loaded_idx_head_allows_rebirth_and_append(monkeypatch):
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

    manager, chain = build_manager()

    result = manager.apply_to_engine(
        spine_version=1,
        spine_active_hash="frozen-head",
        slots=(("CORE", "original"),),
    )

    assert result["status"] == "ok"
    assert result["admission"]["code"] == "IDX_MATCH"
    assert result["config"]["active_hash"] == "frozen-head"
    assert rebirth_calls == ["MANUAL_OVERRIDE"]
    assert len(chain.entries) == 1
