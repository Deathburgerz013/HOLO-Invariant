from holosim.extraction_claim_binding import (
    ExtractionClaimBindingError,
    build_extraction_claim_binding,
    verify_extraction_claim_binding,
)


def test_binding_preserves_exact_extraction_and_claim_identity():
    binding = build_extraction_claim_binding(
        extraction_hash="a" * 64,
        claim_id="claim.correction-preserves-record",
    )

    assert binding["extraction_hash"] == "a" * 64
    assert binding["claim_id"] == "claim.correction-preserves-record"
    assert binding["truth_claimed"] is False
    assert binding["accepted"] is False
    assert binding["write_authority"] == "NONE"


def test_tampered_claim_id_fails_verification():
    import pytest
    binding = build_extraction_claim_binding(extraction_hash="a" * 64, claim_id="claim.original")
    binding["claim_id"] = "claim.forged"
    with pytest.raises(ExtractionClaimBindingError):
        verify_extraction_claim_binding(binding)


def test_rehashed_forged_authority_fails_verification():
    import pytest
    from holosim.canonical import stable_hash
    binding = build_extraction_claim_binding(extraction_hash="a" * 64, claim_id="claim.original")
    binding["write_authority"] = "GRANTED"
    body = {key: value for key, value in binding.items() if key != "binding_hash"}
    binding["binding_hash"] = stable_hash(body)
    with pytest.raises(ExtractionClaimBindingError, match="internally inconsistent"):
        verify_extraction_claim_binding(binding)


def test_rehashed_forged_truth_claim_fails_verification():
    import pytest
    from holosim.canonical import stable_hash
    binding = build_extraction_claim_binding(extraction_hash="a" * 64, claim_id="claim.original")
    binding["truth_claimed"] = True
    body = {key: value for key, value in binding.items() if key != "binding_hash"}
    binding["binding_hash"] = stable_hash(body)
    with pytest.raises(ExtractionClaimBindingError, match="internally inconsistent"):
        verify_extraction_claim_binding(binding)


def test_binding_for_different_extraction_fails_correspondence():
    import pytest
    from holosim.extraction_claim_binding import verify_extraction_claim_correspondence
    binding = build_extraction_claim_binding(extraction_hash="a" * 64, claim_id="claim.original")
    with pytest.raises(ExtractionClaimBindingError, match="extraction"):
        verify_extraction_claim_correspondence(binding, extraction_hash="b" * 64, claim_id="claim.original")


def test_binding_for_different_claim_fails_correspondence():
    import pytest
    binding = build_extraction_claim_binding(extraction_hash="a" * 64, claim_id="claim.original")
    from holosim.extraction_claim_binding import verify_extraction_claim_correspondence
    with pytest.raises(ExtractionClaimBindingError, match="claim"):
        verify_extraction_claim_correspondence(binding, extraction_hash="a" * 64, claim_id="claim.different")


def test_exact_extraction_and_claim_correspondence_verifies():
    from holosim.extraction_claim_binding import verify_extraction_claim_correspondence
    binding = build_extraction_claim_binding(extraction_hash="a" * 64, claim_id="claim.original")
    assert verify_extraction_claim_correspondence(binding, extraction_hash="a" * 64, claim_id="claim.original") is True
