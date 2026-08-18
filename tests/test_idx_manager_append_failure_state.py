from hashlib import sha256

import pytest

import holosim.idx_manager as idx_manager_module
from holosim.idx_manager import IDXManager


def digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class FailingChain:
    def __init__(self):
        self.calls = []

    def append(self, payload, *, compress):
        self.calls.append((payload, compress))
        raise RuntimeError("simulated chain write failure")


def build_manager(chain) -> IDXManager:
    manager = IDXManager(chain=chain)
    manager.active_hash = "previous-head"
    manager.parse_spine(
        "IDX:v=1;n=1\n"
        f"S1=CORE@{digest('original')}\n"
        "ACTIVE_HASH=frozen-head\n"
    )
    return manager


def test_chain_append_failure_preserves_previous_manager_head(
    monkeypatch,
):
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

    chain = FailingChain()
    manager = build_manager(chain)

    with pytest.raises(
        RuntimeError,
        match="simulated chain write failure",
    ):
        manager.apply_to_engine(
            spine_version=1,
            spine_active_hash="frozen-head",
            slots=(("CORE", "original"),),
        )

    assert manager.active_hash == "previous-head"
    assert len(chain.calls) == 1

    attempted_record, compress = chain.calls[0]
    assert attempted_record["active_hash"] == "frozen-head"
    assert attempted_record["config"]["active_hash"] == "frozen-head"
    assert compress is True