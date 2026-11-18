
from unittest.mock import patch

import pytest

from holosim.core import HoloChain
from holosim.information_currency import project_information_currency


def test_projection_preserves_effective_claim_and_boundaries(tmp_path):
    path = tmp_path / "chain.jsonl"
    chain = HoloChain(path)
    original = chain.append({"claim": "Original."})
    correction = chain.correct(
        original["idx"],
        {"claim": "Corrected."},
        reason="New evidence.",
    )
    before = path.read_bytes()

    result = project_information_currency(chain)

    assert path.read_bytes() == before
    assert result["source_root_hash"] == correction["hash"]
    assert result["source_verified"] is True
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert len(result["claims"]) == 1

    claim = result["claims"][0]
    assert claim["idx"] == original["idx"]
    assert claim["content"] == {"claim": "Corrected."}
    assert claim["corrected_by"] == correction["idx"]
    assert claim["correction_history"] == [correction["idx"]]
    assert claim["recorded_status"] == "UNCHECKED"
    assert claim["environmental_currency"] == "UNKNOWN"


def test_projection_preserves_revalidation_without_claiming_truth(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")
    original = chain.append({"claim": "Recorded condition."})
    revalidation = chain.revalidate(
        original["idx"],
        outcome="HELD",
        evidence="Recorded supporting observation.",
        method="manual-review",
    )

    result = project_information_currency(chain)
    claim = result["claims"][0]

    assert result["source_root_hash"] == revalidation["hash"]
    assert claim["recorded_status"] == "HELD"
    assert claim["revalidated_by"] == revalidation["idx"]
    assert claim["revalidation_history"] == [revalidation["idx"]]
    assert claim["environmental_currency"] == "UNKNOWN"
    assert result["truth_claimed"] is False
    assert result["accepted"] is False


def test_correction_supersedes_prior_revalidation(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")
    original = chain.append({"claim": "Original condition."})
    prior = chain.revalidate(
        original["idx"],
        outcome="HELD",
        evidence="Earlier observation.",
        method="manual-review",
    )
    correction = chain.correct(
        original["idx"],
        {"claim": "Revised condition."},
        reason="New observation.",
    )

    result = project_information_currency(chain)
    claim = result["claims"][0]

    assert result["source_root_hash"] == correction["hash"]
    assert claim["content"] == {"claim": "Revised condition."}
    assert claim["corrected_by"] == correction["idx"]
    assert claim["revalidation_history"] == [prior["idx"]]
    assert claim["recorded_status"] == "STALE"
    assert claim["revalidated_by"] is None
    assert claim["environmental_currency"] == "UNKNOWN"


def test_revalidation_of_corrected_content_restores_recorded_status(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")
    original = chain.append({"claim": "Original."})
    prior = chain.revalidate(
        original["idx"],
        outcome="HELD",
        evidence="Earlier observation.",
        method="manual-review",
    )
    correction = chain.correct(
        original["idx"],
        {"claim": "Corrected."},
        reason="New evidence.",
    )
    current = chain.revalidate(
        original["idx"],
        outcome="HELD",
        evidence="Observation of corrected content.",
        method="manual-review",
    )

    result = project_information_currency(chain)
    claim = result["claims"][0]

    assert result["source_root_hash"] == current["hash"]
    assert claim["content"] == {"claim": "Corrected."}
    assert claim["corrected_by"] == correction["idx"]
    assert claim["recorded_status"] == "HELD"
    assert claim["revalidated_by"] == current["idx"]
    assert claim["revalidation_history"] == [prior["idx"], current["idx"]]
    assert claim["environmental_currency"] == "UNKNOWN"
    assert result["truth_claimed"] is False


def test_projection_rejects_source_change_during_verification(tmp_path):
    import holosim.information_currency as module

    chain = HoloChain(tmp_path / "chain.jsonl")
    chain.append({"claim": "Initial."})
    original_verify = module.verify_continuity_checkpoint_against_chain

    def change_source_then_verify(checkpoint, source_chain):
        source_chain.append({"claim": "Changed during verification."})
        return original_verify(checkpoint, source_chain)

    with patch.object(
        module,
        "verify_continuity_checkpoint_against_chain",
        side_effect=change_source_then_verify,
    ):
        with pytest.raises(
            ValueError,
            match="does not match verified source chain",
        ):
            module.project_information_currency(chain)


def test_projection_exposes_source_bound_revalidation_provenance(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")
    original = chain.append({"claim": "original"})
    check = chain.revalidate(
        original["idx"],
        outcome="HELD",
        evidence="observed evidence",
        method="manual-review",
    )

    projection = project_information_currency(chain)
    claim = projection["claims"][0]

    assert claim["revalidations"] == [
        {
            "idx": check["idx"],
            "outcome": "HELD",
            "method": "manual-review",
            "evidence": "observed evidence",
            "subject_hash": claim["content_hash"],
            "subject_correction_idx": None,
            "current": True,
        }
    ]


def test_projection_marks_superseded_revalidation_not_current(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")
    original = chain.append({"claim": "Original."})
    prior = chain.revalidate(
        original["idx"],
        outcome="HELD",
        evidence="Earlier observation.",
        method="manual-review",
    )
    correction = chain.correct(
        original["idx"],
        {"claim": "Corrected."},
        reason="New evidence.",
    )

    projection = project_information_currency(chain)
    claim = projection["claims"][0]

    assert projection["source_root_hash"] == correction["hash"]
    assert claim["recorded_status"] == "STALE"
    assert claim["revalidated_by"] is None
    assert claim["revalidations"][0]["idx"] == prior["idx"]
    assert claim["revalidations"][0]["current"] is False
    assert claim["revalidations"][0]["subject_correction_idx"] is None
    assert claim["environmental_currency"] == "UNKNOWN"


def test_projection_rejects_source_change_during_provenance(tmp_path):
    chain = HoloChain(tmp_path / "chain.jsonl")
    chain.append({"claim": "Original."})

    original_view = chain._revalidation_view

    def change_source_during_view(entries=None):
        result = original_view(entries)

        # Checkpoint reconstruction supplies tuple entries.
        # The projection's explicit provenance reconstruction supplies
        # a list. Mutate only at the latter boundary.
        if isinstance(entries, list):
            chain.append({"claim": "Concurrent addition."})

        return result

    with patch.object(
        chain,
        "_revalidation_view",
        side_effect=change_source_during_view,
    ):
        with pytest.raises(
            ValueError,
            match="Projection source changed during reconstruction",
        ):
            project_information_currency(chain)
