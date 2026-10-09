import pytest

from holosim.continuity_checkpoint import build_continuity_checkpoint
from holosim.core import HoloChain


def test_checkpoint_rejects_source_change_during_reconstruction(
    tmp_path, monkeypatch
):
    chain = HoloChain(tmp_path / "memory.jsonl")
    chain.append({"claim": "Original observation"})

    original_admit = chain._admit_verified_entries

    def append_during_reconstruction(entries):
        chain.append({"claim": "Concurrent observation"})
        return original_admit(entries)

    monkeypatch.setattr(
        chain,
        "_admit_verified_entries",
        append_during_reconstruction,
    )

    with pytest.raises(ValueError, match="changed during reconstruction"):
        build_continuity_checkpoint(chain)
