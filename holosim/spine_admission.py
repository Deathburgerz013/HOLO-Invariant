"""Deterministic, read-only admission checks for Spine Storage V1 candidates.

The candidate bytes are never rewritten.  A receipt binds their exact SHA-256
and a derived canonical representation of the fields used by this validator.
Neither an admission decision nor a hash establishes external truth or grants
write or execution authority.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .canonical import stable_hash
from .spine_protocol import SpineDocument, analyze_rail_structure, parse_spine_text


RECEIPT_TYPE = "holo_spine_admission_receipt"
RECEIPT_VERSION = 1
TEMPLATE_VERSION = "SPINE_STORAGE_V1"
INFORMATION_CLASSES = {
    "OBSERVATION", "CLAIM", "EVIDENCE", "VERIFICATION", "INFERENCE",
    "RULE", "UNCERTAINTY", "CORRECTION", "TERMINAL",
}
ENTRY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")
FIELD = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]*)\s*:\s*(?P<value>.*)$")


class SpineAdmissionError(ValueError):
    """Raised when receipt inputs are not usable as a candidate Spine."""


def _rail_body(line: str) -> str | None:
    match = re.match(r"^(?:\||│)\s*(?:\||│)\s?(.*)$", line)
    return None if match is None else match.group(1).rstrip()


def _compartments(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    current: list[str] = []
    for line in text.splitlines():
        body = _rail_body(line)
        if body is None:
            continue
        if re.fullmatch(r"\}?={3,}\|?", body.strip()):
            if current:
                result.append(_parse_compartment(current))
                current = []
            continue
        current.append(body)
    if current:
        result.append(_parse_compartment(current))
    return [item for item in result if item["name"]]


def _parse_compartment(lines: list[str]) -> dict[str, Any]:
    meaningful = [line.strip() for line in lines if line.strip()]
    if not meaningful:
        return {"name": "", "fields": {}}
    name = meaningful[0].strip("|").strip()
    fields: dict[str, str] = {}
    duplicates: list[str] = []
    for line in meaningful[1:]:
        match = FIELD.fullmatch(line)
        if match is None:
            continue
        key, value = match.group("name"), match.group("value").strip()
        if key in fields:
            duplicates.append(key)
        else:
            fields[key] = value
    return {"name": name, "fields": fields, "duplicate_fields": duplicates}


def _refs(value: str) -> list[str]:
    cleaned = value.strip().strip("[]").strip()
    if cleaned in {"", "NONE", "UNKNOWN"}:
        return []
    return [item.strip() for item in cleaned.split(",") if item.strip()]


def _required(fields: dict[str, str], names: tuple[str, ...], prefix: str,
              errors: list[str]) -> None:
    for name in names:
        if not fields.get(name):
            errors.append(f"{prefix}:missing_field:{name}")


def build_spine_admission_receipt(
    candidate: str | SpineDocument,
    *,
    validator_id: str,
    contributor_id: str | None = None,
) -> dict[str, Any]:
    """Validate one immutable candidate and return a deterministic receipt."""
    if type(validator_id) is not str or not validator_id.strip():
        raise SpineAdmissionError("validator_id must be a nonempty plain string")
    if contributor_id is not None and (
        type(contributor_id) is not str or not contributor_id.strip()
    ):
        raise SpineAdmissionError("contributor_id must be a nonempty plain string")
    document = parse_spine_text(candidate) if type(candidate) is str else candidate
    if not isinstance(document, SpineDocument):
        raise SpineAdmissionError("candidate must be Spine text or a SpineDocument")

    errors: list[str] = []
    compartments = _compartments(document.raw_text)
    counts = Counter(item["name"] for item in compartments)
    by_name = {name: [item for item in compartments if item["name"] == name]
               for name in counts}
    required_names = ("SPINE_META", "RECOGNITION", "COLLECTION_CONTRACT",
                      "COLLECTION_STATUS", "IDX_ADMISSION", "TERMINAL")
    for name in required_names:
        if counts[name] != 1:
            errors.append(f"compartment_count:{name}:{counts[name]}")
    if counts["ENTRY"] < 1:
        errors.append("compartment_count:ENTRY:0")
    for item in compartments:
        for field in item["duplicate_fields"]:
            errors.append(f"{item['name']}:duplicate_field:{field}")

    meta = by_name.get("SPINE_META", [{"fields": {}}])[0]["fields"]
    _required(meta, ("TEMPLATE_VERSION", "SPINE_ID", "STATE", "CREATED_BY"),
              "SPINE_META", errors)
    if meta.get("TEMPLATE_VERSION") != TEMPLATE_VERSION:
        errors.append("SPINE_META:unsupported_template_version")
    if meta.get("STATE") != "CANDIDATE":
        errors.append("SPINE_META:state_must_be_candidate")
    spine_id = meta.get("SPINE_ID", "")
    if spine_id and ENTRY_ID.fullmatch(spine_id) is None:
        errors.append("SPINE_META:invalid_spine_id")

    entries = by_name.get("ENTRY", [])
    ids: list[str] = []
    parsed_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        fields = entry["fields"]
        prefix = f"ENTRY[{index}]"
        _required(fields, ("ENTRY_ID", "ENTITY_ID", "ENTITY_TYPE",
                           "SOURCE_STATE_ID", "INFORMATION_CLASS", "SOURCE",
                           "VERIFICATION_STATUS", "EVIDENCE_REFS",
                           "DERIVED_FROM", "CORRECTS_ENTRY", "UNCERTAINTY"),
                  prefix, errors)
        entry_id = fields.get("ENTRY_ID", "")
        if entry_id and ENTRY_ID.fullmatch(entry_id) is None:
            errors.append(f"{prefix}:invalid_entry_id")
        ids.append(entry_id)
        info_class = fields.get("INFORMATION_CLASS", "")
        if info_class not in INFORMATION_CLASSES:
            errors.append(f"{prefix}:invalid_information_class:{info_class}")
        parsed_entries.append({"id": entry_id, "class": info_class, "fields": fields})
    for duplicate, count in Counter(ids).items():
        if duplicate and count > 1:
            errors.append(f"duplicate_entry_id:{duplicate}")

    positions = {entry_id: index for index, entry_id in enumerate(ids) if entry_id}
    classes = {item["id"]: item["class"] for item in parsed_entries if item["id"]}
    for index, item in enumerate(parsed_entries):
        fields, entry_id = item["fields"], item["id"]
        for ref in _refs(fields.get("EVIDENCE_REFS", "")):
            if ref not in positions:
                errors.append(f"ENTRY[{index}]:missing_evidence_ref:{ref}")
            elif classes[ref] != "EVIDENCE":
                errors.append(f"ENTRY[{index}]:evidence_ref_not_evidence:{ref}")
        for ref in _refs(fields.get("DERIVED_FROM", "")):
            if ref not in positions:
                errors.append(f"ENTRY[{index}]:missing_derived_ref:{ref}")
        corrects = _refs(fields.get("CORRECTS_ENTRY", ""))
        if item["class"] == "CORRECTION" and len(corrects) != 1:
            errors.append(f"ENTRY[{index}]:correction_requires_one_target")
        if item["class"] != "CORRECTION" and corrects:
            errors.append(f"ENTRY[{index}]:non_correction_has_target")
        for ref in corrects:
            if ref not in positions:
                errors.append(f"ENTRY[{index}]:missing_correction_target:{ref}")
            elif positions[ref] >= index:
                errors.append(f"ENTRY[{index}]:correction_target_not_prior:{ref}")

    rail = analyze_rail_structure(document.raw_text)
    if not rail["continuous"]:
        errors.append("rail:not_continuous")
    admission = by_name.get("IDX_ADMISSION", [{"fields": {}}])[0]["fields"]
    declared_hash = admission.get("SPINE_SHA256", "")
    if declared_hash not in {"NONE", "CANDIDATE_BYTES_HASH_IN_RECEIPT"}:
        errors.append("IDX_ADMISSION:self_referential_spine_hash_not_permitted")
    if admission.get("ADMISSION_STATUS") != "CANDIDATE":
        errors.append("IDX_ADMISSION:status_must_be_candidate")

    errors = sorted(set(errors))
    contributors = sorted({value for value in (
        contributor_id, meta.get("CREATED_BY"),
        *(item["fields"].get("ENTITY_ID") for item in parsed_entries),
    ) if value})
    canonical_candidate = {
        "template_version": meta.get("TEMPLATE_VERSION"),
        "spine_id": spine_id,
        "compartments": compartments,
    }
    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "validator_id": validator_id,
        "candidate_source_sha256": document.source_sha256,
        "candidate_size_bytes": len(document.raw_bytes),
        "canonical_candidate_sha256": stable_hash(canonical_candidate),
        "spine_id": spine_id or None,
        "template_version": meta.get("TEMPLATE_VERSION"),
        "contributors": contributors,
        "checks": {
            "header": True,
            "rail": rail["continuous"],
            "structure": not any(error.startswith("compartment_count:") for error in errors),
            "identifiers_classes_references": not any(
                token in error for error in errors for token in
                ("entry_id", "information_class", "_ref", "correction_")
            ),
            "candidate_hash_recalculated": True,
        },
        "errors": errors,
        "decision": "ADMITTED" if not errors else "REJECTED",
        "accepted_as_truth": False,
        "canonical_mutation": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Admission establishes conformance to declared structural checks only; "
            "it does not establish external truth, completeness, or authority."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def validate_spine_admission_receipt(receipt: dict[str, Any]) -> bool:
    """Verify exact schema, internal decision consistency, and receipt hash."""
    if type(receipt) is not dict:
        raise SpineAdmissionError("receipt must be a plain dictionary")
    required = {
        "type", "version", "validator_id", "candidate_source_sha256",
        "candidate_size_bytes", "canonical_candidate_sha256", "spine_id",
        "template_version", "contributors", "checks", "errors", "decision",
        "accepted_as_truth", "canonical_mutation", "write_authority",
        "execution_authority", "interpretation_notice", "receipt_hash",
    }
    if set(receipt) != required:
        raise SpineAdmissionError("receipt fields do not match the versioned schema")
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise SpineAdmissionError("receipt type or version is invalid")
    errors = receipt["errors"]
    if type(errors) is not list or errors != sorted(set(errors)):
        raise SpineAdmissionError("receipt errors must be sorted and unique")
    if receipt["decision"] != ("ADMITTED" if not errors else "REJECTED"):
        raise SpineAdmissionError("receipt decision contradicts errors")
    if (receipt["accepted_as_truth"] is not False or
            receipt["canonical_mutation"] is not False or
            receipt["write_authority"] != "NONE" or
            receipt["execution_authority"] != "NONE"):
        raise SpineAdmissionError("receipt grants forbidden authority")
    body = dict(receipt)
    supplied = body.pop("receipt_hash")
    if supplied != stable_hash(body):
        raise SpineAdmissionError("receipt hash mismatch")
    return True
