import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


SCHEMA_ROOT = Path("schemas")

PACKET_SCHEMA = (
    SCHEMA_ROOT / "idx-spine-packet.schema.json"
)

RECEIPT_SCHEMA = (
    SCHEMA_ROOT / "idx-check-receipt.schema.json"
)


def reject_duplicate_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(
                f"duplicate JSON key: {key}"
            )

        result[key] = value

    return result


def load_schema(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate_keys,
    )


@pytest.mark.parametrize(
    "path",
    [
        PACKET_SCHEMA,
        RECEIPT_SCHEMA,
    ],
)
def test_public_idx_schema_exists_and_is_valid_json(
    path: Path,
):
    schema = load_schema(path)

    assert schema["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert schema["type"] == "object"

    if path == PACKET_SCHEMA:
        assert schema["additionalProperties"] is False
    else:
        assert "oneOf" in schema


def test_packet_schema_closes_the_public_input_contract():
    schema = load_schema(PACKET_SCHEMA)

    assert schema["$id"].endswith(
        "/idx-spine-packet.schema.json"
    )
    assert schema["required"] == [
        "version",
        "active_hash",
        "slots",
    ]

    properties = schema["properties"]

    assert properties["version"] == {
        "type": "integer",
        "minimum": 1,
    }
    assert properties["active_hash"] == {
        "type": "string",
        "minLength": 1,
    }

    slots = properties["slots"]

    assert slots["type"] == "array"
    assert slots["minItems"] == 1

    slot = slots["items"]

    assert slot["type"] == "object"
    assert slot["additionalProperties"] is False
    assert slot["required"] == [
        "name",
        "payload",
    ]
    assert slot["properties"]["name"] == {
        "type": "string",
        "minLength": 1,
    }
    assert slot["properties"]["payload"] == {
        "type": "string",
    }


def test_receipt_schema_separates_results_from_errors():
    schema = load_schema(RECEIPT_SCHEMA)

    assert schema["$id"].endswith(
        "/idx-check-receipt.schema.json"
    )

    branches = schema["oneOf"]

    assert len(branches) == 2

    result_branch, error_branch = branches

    assert result_branch["additionalProperties"] is False
    assert result_branch["required"] == [
        "status",
        "code",
        "fused",
        "slot",
        "expected",
        "observed",
    ]
    assert result_branch["properties"]["status"] == {
        "enum": [
            "PASS",
            "ABORT",
        ]
    }
    assert result_branch["properties"]["code"] == {
        "type": "string",
        "minLength": 1,
    }
    assert result_branch["properties"]["fused"] == {
        "const": False,
    }

    nullable_string = {
        "type": [
            "string",
            "null",
        ]
    }

    assert result_branch["properties"]["slot"] == (
        nullable_string
    )
    assert result_branch["properties"]["expected"] == (
        nullable_string
    )
    assert result_branch["properties"]["observed"] == (
        nullable_string
    )

    assert error_branch["additionalProperties"] is False
    assert error_branch["required"] == [
        "status",
        "code",
        "fused",
        "error",
    ]
    assert error_branch["properties"]["status"] == {
        "const": "ERROR",
    }
    assert error_branch["properties"]["code"] == {
        "const": "IDX_PACKET_INVALID",
    }
    assert error_branch["properties"]["fused"] == {
        "const": False,
    }
    assert error_branch["properties"]["error"] == {
        "type": "string",
        "minLength": 1,
    }

def test_public_schemas_pass_draft_2020_12_metaschema():
    Draft202012Validator.check_schema(
        load_schema(PACKET_SCHEMA)
    )
    Draft202012Validator.check_schema(
        load_schema(RECEIPT_SCHEMA)
    )


def test_packet_schema_accepts_declared_contract():
    validator = Draft202012Validator(
        load_schema(PACKET_SCHEMA)
    )

    validator.validate(
        {
            "version": 1,
            "active_hash": "frozen-head",
            "slots": [
                {
                    "name": "CORE",
                    "payload": "original",
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "packet",
    [
        {
            "version": 0,
            "active_hash": "frozen-head",
            "slots": [
                {
                    "name": "CORE",
                    "payload": "original",
                }
            ],
        },
        {
            "version": 1,
            "active_hash": "frozen-head",
            "slots": [],
        },
        {
            "version": 1,
            "active_hash": "frozen-head",
            "slots": [
                {
                    "name": "CORE",
                    "payload": "original",
                    "authority": "undeclared",
                }
            ],
        },
    ],
)
def test_packet_schema_rejects_out_of_contract_data(
    packet,
):
    validator = Draft202012Validator(
        load_schema(PACKET_SCHEMA)
    )

    with pytest.raises(ValidationError):
        validator.validate(packet)


@pytest.mark.parametrize(
    "receipt",
    [
        {
            "status": "PASS",
            "code": "IDX_MATCH",
            "fused": False,
            "slot": None,
            "expected": None,
            "observed": None,
        },
        {
            "status": "ABORT",
            "code": "SLOT_HASH_MISMATCH",
            "fused": False,
            "slot": "CORE",
            "expected": "expected-hash",
            "observed": "observed-hash",
        },
        {
            "status": "ERROR",
            "code": "IDX_PACKET_INVALID",
            "fused": False,
            "error": "packet slots are missing",
        },
    ],
)
def test_receipt_schema_accepts_cli_receipts(
    receipt,
):
    validator = Draft202012Validator(
        load_schema(RECEIPT_SCHEMA)
    )

    validator.validate(receipt)


def test_receipt_schema_rejects_undeclared_authority():
    validator = Draft202012Validator(
        load_schema(RECEIPT_SCHEMA)
    )

    with pytest.raises(ValidationError):
        validator.validate(
            {
                "status": "PASS",
                "code": "IDX_MATCH",
                "fused": False,
                "slot": None,
                "expected": None,
                "observed": None,
                "authority": "granted",
            }
        )
