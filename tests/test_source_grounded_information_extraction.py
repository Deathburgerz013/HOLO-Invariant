import pytest

from holosim.hook_contract import build_hook_request, build_hook_result
from holosim.source_grounded_information_extraction import (
    EXTRACTION_TYPE,
    EXTRACTION_VERSION,
    SourceGroundedInformationExtractionError,
    build_source_grounded_extraction,
    verify_source_grounded_extraction,
)


def _observed_result():
    request = build_hook_request(
        hook_id="source-reader",
        action="observe",
        reference="document:a",
        payload={},
    )
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={
            "document": {
                "text": "Correction preserves the earlier record."
            }
        },
    )
    return request, result


def test_claimed_text_must_equal_exact_declared_source_span():
    request, result = _observed_result()

    with pytest.raises(
        SourceGroundedInformationExtractionError,
        match="source span",
    ):
        build_source_grounded_extraction(
            request=request,
            result=result,
            source_path=["document", "text"],
            start_offset=0,
            end_offset=10,
            extracted_text="Contradiction",
        )



def _valid_extraction():
    request, result = _observed_result()
    text = "Correction"
    extraction = build_source_grounded_extraction(
        request=request,
        result=result,
        source_path=["document", "text"],
        start_offset=0,
        end_offset=len(text),
        extracted_text=text,
    )
    return request, result, extraction


def test_valid_extraction_reconstructs_from_original_source():
    request, result, extraction = _valid_extraction()

    assert extraction["extracted_text"] == "Correction"
    assert extraction["source_result_hash"] == result["result_hash"]
    assert verify_source_grounded_extraction(
        extraction,
        request=request,
        result=result,
    ) is True


def test_tampered_extracted_text_fails_closed():
    request, result, extraction = _valid_extraction()
    extraction["extracted_text"] = "Contradiction"

    with pytest.raises(SourceGroundedInformationExtractionError):
        verify_source_grounded_extraction(
            extraction,
            request=request,
            result=result,
        )


def test_tampered_source_offset_fails_closed():
    request, result, extraction = _valid_extraction()
    extraction["start_offset"] = 1

    with pytest.raises(SourceGroundedInformationExtractionError):
        verify_source_grounded_extraction(
            extraction,
            request=request,
            result=result,
        )


def test_extraction_cannot_verify_against_different_hook_result():
    request, _, extraction = _valid_extraction()
    other_result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={
            "document": {
                "text": "Correction came from a different observation."
            }
        },
    )

    with pytest.raises(SourceGroundedInformationExtractionError):
        verify_source_grounded_extraction(
            extraction,
            request=request,
            result=other_result,
        )


def test_unresolved_source_path_fails_closed():
    request, result = _observed_result()
    with pytest.raises(SourceGroundedInformationExtractionError, match="source_path does not resolve"):
        build_source_grounded_extraction(request=request, result=result, source_path=["document", "missing"], start_offset=0, end_offset=1, extracted_text="x")


def test_resolved_source_must_be_text():
    request = build_hook_request(hook_id="source-reader", action="observe", reference="document:a", payload={})
    result = build_hook_result(request=request, status="OBSERVED", evidence={"document": {"value": 42}})
    with pytest.raises(SourceGroundedInformationExtractionError, match="source value must be text"):
        build_source_grounded_extraction(request=request, result=result, source_path=["document", "value"], start_offset=0, end_offset=1, extracted_text="4")


def test_failed_hook_result_cannot_be_extracted():
    request = build_hook_request(hook_id="source-reader", action="observe", reference="document:a", payload={})
    result = build_hook_result(request=request, status="FAILED", evidence={"document": {"text": "Correction"}})
    with pytest.raises(SourceGroundedInformationExtractionError, match="must be OBSERVED"):
        build_source_grounded_extraction(request=request, result=result, source_path=["document", "text"], start_offset=0, end_offset=10, extracted_text="Correction")


def test_unavailable_hook_result_cannot_be_extracted():
    request = build_hook_request(hook_id="source-reader", action="observe", reference="document:a", payload={})
    result = build_hook_result(request=request, status="UNAVAILABLE", evidence={"document": {"text": "Correction"}})
    with pytest.raises(SourceGroundedInformationExtractionError, match="must be OBSERVED"):
        build_source_grounded_extraction(request=request, result=result, source_path=["document", "text"], start_offset=0, end_offset=10, extracted_text="Correction")


@pytest.mark.parametrize("start_offset,end_offset", [(False, 1), (0, True)])
def test_boolean_source_offsets_fail_closed(start_offset, end_offset):
    request, result = _observed_result()
    with pytest.raises(SourceGroundedInformationExtractionError, match="source span is invalid"):
        build_source_grounded_extraction(request=request, result=result, source_path=["document", "text"], start_offset=start_offset, end_offset=end_offset, extracted_text="x")


@pytest.mark.parametrize("start_offset,end_offset", [(-1, 1), (0, 0), (5, 4), (0, 10000)])
def test_out_of_bounds_source_spans_fail_closed(start_offset, end_offset):
    request, result = _observed_result()
    with pytest.raises(SourceGroundedInformationExtractionError, match="source span is invalid"):
        build_source_grounded_extraction(request=request, result=result, source_path=["document", "text"], start_offset=start_offset, end_offset=end_offset, extracted_text="x")


def test_extraction_grants_no_truth_acceptance_or_authority():
    request, result, extraction = _valid_extraction()
    assert extraction["truth_claimed"] is False
    assert extraction["accepted"] is False
    assert extraction["write_authority"] == "NONE"
    assert extraction["execution_authority"] == "NONE"


def test_rehashed_forged_authority_fails_verification():
    from holosim.canonical import stable_hash
    request, result, extraction = _valid_extraction()
    extraction["write_authority"] = "GRANTED"
    body = {key: value for key, value in extraction.items() if key != "extraction_hash"}
    extraction["extraction_hash"] = stable_hash(body)
    with pytest.raises(SourceGroundedInformationExtractionError, match="internally inconsistent"):
        verify_source_grounded_extraction(extraction, request=request, result=result)


def test_extraction_schema_identity_is_explicit_and_versioned():
    assert EXTRACTION_TYPE == "source_grounded_information_extraction"
    assert EXTRACTION_VERSION == 1


def test_rehashed_forged_truth_claim_fails_verification():
    from holosim.canonical import stable_hash
    request, result, extraction = _valid_extraction()
    extraction["truth_claimed"] = True
    body = {key: value for key, value in extraction.items() if key != "extraction_hash"}
    extraction["extraction_hash"] = stable_hash(body)
    with pytest.raises(SourceGroundedInformationExtractionError, match="internally inconsistent"):
        verify_source_grounded_extraction(extraction, request=request, result=result)
