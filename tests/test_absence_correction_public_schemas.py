"""Public schema tests for absence-correction receipts."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from test_absence_claim_correction_binding import (
    _build as build_binding,
    _inputs as binding_inputs,
)
from test_persisted_absence_correction_attestation import (
    _build as build_attestation,
    _inputs as attestation_inputs,
)

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def _validator(filename):
    schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    return Draft202012Validator(schema), schema


@pytest.mark.parametrize("kind", ["binding", "attestation"])
def test_public_absence_correction_schema_accepts_real_receipt(kind, tmp_path):
    if kind == "binding":
        validator, schema = _validator(
            "absence-claim-correction-binding.schema.json"
        )
        receipt = build_binding(*binding_inputs())
    else:
        validator, schema = _validator(
            "persisted-absence-correction-attestation.schema.json"
        )
        receipt = build_attestation(*attestation_inputs(tmp_path))

    validator.validate(receipt)

    for field in schema["required"]:
        altered = deepcopy(receipt)
        del altered[field]
        assert not validator.is_valid(altered), field

    altered = deepcopy(receipt)
    altered["undeclared_field"] = True
    assert not validator.is_valid(altered)

    for field, definition in schema["properties"].items():
        if definition.get("const") is False:
            altered = deepcopy(receipt)
            altered[field] = True
            assert not validator.is_valid(altered), field
        elif definition.get("const") == "NONE":
            altered = deepcopy(receipt)
            altered[field] = "GRANTED"
            assert not validator.is_valid(altered), field

    if kind == "attestation":
        for invalid in ("", None, 123, [], {}):
            altered = deepcopy(receipt)
            altered["record_id"] = invalid
            assert not validator.is_valid(altered)

        altered = deepcopy(receipt)
        altered["post_persistence_association"] = False
        assert not validator.is_valid(altered)
