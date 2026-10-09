from holosim.continuity_checkpoint import build_continuity_checkpoint
from holosim.core import HoloChain


def test_checkpoint_uses_one_source_snapshot_plus_final_check(tmp_path, monkeypatch):
    chain = HoloChain(tmp_path / "memory.jsonl")
    chain.append({"claim": "A"})
    chain.append({"claim": "B"})

    original_load = chain.load_and_verify
    reads = 0

    def counted_load():
        nonlocal reads
        reads += 1
        return original_load()

    monkeypatch.setattr(chain, "load_and_verify", counted_load)

    checkpoint = build_continuity_checkpoint(chain)

    assert checkpoint["source"]["total_entries"] == 2
    assert len(checkpoint["claims"]) == 2
    assert reads == 2
