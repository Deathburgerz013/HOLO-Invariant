"""Exact source-grounded information extraction for HOLO/Sim.

This boundary binds declared extracted text to an exact character span inside
observed hook evidence. It does not interpret the text, establish truth, accept
a result, grant authority, or mutate any source.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.hook_contract import HookContractError, validate_hook_result


EXTRACTION_TYPE = "source_grounded_information_extraction"
EXTRACTION_VERSION = 1


class SourceGroundedInformationExtractionError(ValueError):
    """Raised when an extraction cannot be grounded in its declared source."""


def _resolve_source_path(
    evidence: Mapping[str, Any],
    source_path: Sequence[str],
) -> str:
    if (
        isinstance(source_path, (str, bytes, bytearray))
        or not isinstance(source_path, Sequence)
        or not source_path
    ):
        raise SourceGroundedInformationExtractionError(
            "source_path must be a non-empty sequence"
        )

    current: Any = evidence
    for component in source_path:
        if type(component) is not str or not component:
            raise SourceGroundedInformationExtractionError(
                "source_path components must be non-empty strings"
            )
        if type(current) is not dict or component not in current:
            raise SourceGroundedInformationExtractionError(
                "source_path does not resolve"
            )
        current = current[component]

    if type(current) is not str:
        raise SourceGroundedInformationExtractionError(
            "resolved source value must be text"
        )
    return current


def build_source_grounded_extraction(
    *,
    request: Mapping[str, Any],
    result: Mapping[str, Any],
    source_path: Sequence[str],
    start_offset: int,
    end_offset: int,
    extracted_text: str,
) -> dict[str, Any]:
    """Bind declared text to one exact span of observed hook evidence."""
    try:
        validate_hook_result(result, request=request)
    except HookContractError as exc:
        raise SourceGroundedInformationExtractionError(
            f"hook result is invalid: {exc}"
        ) from exc

    if result["status"] != "OBSERVED":
        raise SourceGroundedInformationExtractionError(
            "hook result must be OBSERVED"
        )

    source_text = _resolve_source_path(result["evidence"], source_path)

    if (
        type(start_offset) is not int
        or type(end_offset) is not int
        or start_offset < 0
        or end_offset <= start_offset
        or end_offset > len(source_text)
    ):
        raise SourceGroundedInformationExtractionError(
            "source span is invalid"
        )

    if type(extracted_text) is not str:
        raise SourceGroundedInformationExtractionError(
            "extracted_text must be text"
        )

    if source_text[start_offset:end_offset] != extracted_text:
        raise SourceGroundedInformationExtractionError(
            "extracted text does not match source span"
        )

    body = {
        "type": EXTRACTION_TYPE,
        "version": EXTRACTION_VERSION,
        "source_result_hash": result["result_hash"],
        "source_path": list(source_path),
        "start_offset": start_offset,
        "end_offset": end_offset,
        "extracted_text": extracted_text,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    try:
        extraction_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise SourceGroundedInformationExtractionError(str(exc)) from exc
    return {**body, "extraction_hash": extraction_hash}


def verify_source_grounded_extraction(
    extraction: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    result: Mapping[str, Any],
) -> bool:
    """Rebuild an extraction from its source and reject semantic tampering."""
    expected_fields = {
        "type", "version", "source_result_hash", "source_path",
        "start_offset", "end_offset", "extracted_text", "truth_claimed",
        "accepted", "write_authority", "execution_authority",
        "extraction_hash",
    }
    if type(extraction) is not dict or set(extraction) != expected_fields:
        raise SourceGroundedInformationExtractionError(
            "extraction fields mismatch"
        )
    if (
        extraction["type"] != EXTRACTION_TYPE
        or extraction["version"] != EXTRACTION_VERSION
    ):
        raise SourceGroundedInformationExtractionError(
            "extraction schema mismatch"
        )

    expected = build_source_grounded_extraction(
        request=request,
        result=result,
        source_path=extraction["source_path"],
        start_offset=extraction["start_offset"],
        end_offset=extraction["end_offset"],
        extracted_text=extraction["extracted_text"],
    )
    if dict(extraction) != expected:
        raise SourceGroundedInformationExtractionError(
            "extraction is internally inconsistent"
        )
    return True
