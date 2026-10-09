from holosim.core import HoloChain


def test_valid_chain_snapshot_is_positively_admitted(tmp_path):
    chain = HoloChain(tmp_path / "memory.jsonl")
    chain.append({"claim": "Observed result"})

    snapshot = chain._load_verified_snapshot()
    entries = snapshot.entries
    admission = chain._admit_verified_entries(snapshot)

    assert admission["decision"] == "ADMITTED"
    assert admission["source"]["total_entries"] == 1
    assert admission["source"]["root_hash"] == entries[-1]["hash"]
    assert admission["accepted_as_truth"] is False
    assert admission["write_authority"] == "NONE"
    assert admission["execution_authority"] == "NONE"
    assert len(admission["claims"]) == 1


def test_tampered_snapshot_cannot_be_admitted(tmp_path):
    import copy
    import pytest

    chain = HoloChain(tmp_path / "memory.jsonl")
    chain.append({"claim": "Original observation"})

    snapshot = chain._load_verified_snapshot()

    # Change the content without updating its recorded hash.
    snapshot.entries[0]["content"] = '{"claim":"Forged observation"}'

    with pytest.raises(ValueError):
        chain._admit_verified_entries(snapshot)


def test_foreign_chain_snapshot_cannot_be_admitted(tmp_path):
    import pytest

    trusted = HoloChain(tmp_path / "trusted.jsonl")
    foreign = HoloChain(tmp_path / "foreign.jsonl")

    trusted.append({"claim": "Trusted observation"})
    foreign.append({"claim": "Different observation"})

    foreign_snapshot = foreign._load_verified_snapshot()

    with pytest.raises(ValueError):
        trusted._admit_verified_entries(foreign_snapshot)


def test_plain_entries_cannot_bypass_snapshot_admission(tmp_path):
    import pytest

    chain = HoloChain(tmp_path / "memory.jsonl")
    chain.append({"claim": "Observation"})

    entries = chain.load_and_verify()

    with pytest.raises((TypeError, ValueError)):
        chain._admit_verified_entries(entries)
