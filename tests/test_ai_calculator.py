from __future__ import annotations

import copy
import hashlib
import json

import pytest

from holosim.ai_calculator import (
    MAX_AST_DEPTH,
    MAX_DECIMAL_PLACES,
    MAX_EXPONENT_ABS,
    MAX_EXPRESSION_UTF8_BYTES,
    MAX_NUMBER_UTF8_BYTES,
    MAX_RESULT_BITS,
    MAX_VARIABLES,
    AICalculatorError,
    calculate_expression,
    validate_calculation_receipt,
)


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def rehash(receipt: dict) -> None:
    body = dict(receipt)
    body.pop("receipt_hash")
    receipt["receipt_hash"] = canonical_hash(body)


def test_integer_arithmetic_and_precedence() -> None:
    receipt = calculate_expression("2 + 3 * 4")

    assert receipt["exact_result"] == {"numerator": "14", "denominator": "1"}
    assert receipt["operation_ids"] == ["MULTIPLY", "ADD"]
    assert receipt["decimal_approximation"] == "14.000000000000"
    validate_calculation_receipt(receipt)


def test_division_is_exact_rational() -> None:
    receipt = calculate_expression("1 / 3", decimal_places=6)

    assert receipt["exact_result"] == {"numerator": "1", "denominator": "3"}
    assert receipt["decimal_approximation"] == "0.333333"
    assert receipt["result_kind"] == "EXACT_RATIONAL"
    validate_calculation_receipt(receipt)


def test_decimal_literals_are_parsed_from_source_exactly() -> None:
    receipt = calculate_expression("0.1 + 0.2", decimal_places=2)

    assert receipt["exact_result"] == {"numerator": "3", "denominator": "10"}
    assert receipt["decimal_approximation"] == "0.30"


def test_scientific_notation_is_exact() -> None:
    receipt = calculate_expression("1e-3 * 2e3", decimal_places=3)

    assert receipt["exact_result"] == {"numerator": "2", "denominator": "1"}
    assert receipt["decimal_approximation"] == "2.000"


def test_variables_accept_integer_decimal_and_fraction_strings() -> None:
    receipt = calculate_expression(
        "whole + decimal + fraction",
        {"whole": 2, "decimal": "0.25", "fraction": "1/2"},
        decimal_places=2,
    )

    assert receipt["exact_result"] == {"numerator": "11", "denominator": "4"}
    assert receipt["variables"]["fraction"] == {
        "numerator": "1",
        "denominator": "2",
    }
    validate_calculation_receipt(receipt)


def test_all_supported_operations() -> None:
    cases = {
        "7 - 10": ("-3", "1", "SUBTRACT"),
        "-5": ("-5", "1", "UNARY_MINUS"),
        "+5": ("5", "1", "UNARY_PLUS"),
        "7 // 2": ("3", "1", "FLOOR_DIVIDE"),
        "7 % 2": ("1", "1", "MODULO"),
        "2 ** -3": ("1", "8", "POWER"),
    }
    for expression, (numerator, denominator, operation) in cases.items():
        receipt = calculate_expression(expression)
        assert receipt["exact_result"] == {
            "numerator": numerator,
            "denominator": denominator,
        }
        assert operation in receipt["operation_ids"]


def test_receipt_is_deterministic_and_inputs_are_not_mutated() -> None:
    variables = {"x": "3/4"}
    original = copy.deepcopy(variables)

    first = calculate_expression("x * 8", variables)
    second = calculate_expression("x * 8", variables)

    assert first == second
    assert variables == original


def test_receipt_denies_premise_validation_acceptance_and_authority() -> None:
    receipt = calculate_expression("x + 1", {"x": 2})

    assert receipt["premise_status"] == "NOT_VALIDATED"
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert "does not prove" in receipt["interpretation_notice"]


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo unsafe')",
        "(1).__class__",
        "[x for x in [1]]",
        "lambda: 1",
        "{'x': 1}",
        "[1, 2]",
        "1 if True else 0",
        "x := 1",
        "True + 1",
        "'1'",
    ],
)
def test_python_execution_and_nonarithmetic_syntax_are_forbidden(expression: str) -> None:
    with pytest.raises(AICalculatorError):
        calculate_expression(expression)


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ("1 / 0", "division by zero"),
        ("1 // 0", "floor division by zero"),
        ("1 % 0", "modulo by zero"),
        ("0 ** -1", "zero cannot"),
        ("4 ** 0.5", "exact integer"),
        (f"2 ** {MAX_EXPONENT_ABS + 1}", "exponent exceeds"),
    ],
)
def test_invalid_arithmetic_fails_closed(expression: str, message: str) -> None:
    with pytest.raises(AICalculatorError, match=message):
        calculate_expression(expression)


def test_unknown_variable_is_rejected() -> None:
    with pytest.raises(AICalculatorError, match="unknown variable"):
        calculate_expression("missing + 1")


@pytest.mark.parametrize("value", [True, 1.5, None, [], {}, "nan", "inf", "1/0"])
def test_invalid_variable_values_are_rejected(value) -> None:
    with pytest.raises(AICalculatorError):
        calculate_expression("x", {"x": value})


@pytest.mark.parametrize("name", ["", "not-valid", "x y", "é", "x" * 129, 7])
def test_invalid_variable_names_are_rejected(name) -> None:
    with pytest.raises(AICalculatorError, match="variable names"):
        calculate_expression("1", {name: 1})


def test_variable_count_limit_is_enforced() -> None:
    variables = {f"x{index}": index for index in range(MAX_VARIABLES + 1)}

    with pytest.raises(AICalculatorError, match="item limit"):
        calculate_expression("1", variables)


def test_numeric_string_byte_limit_is_enforced_before_parsing() -> None:
    with pytest.raises(AICalculatorError, match="numeric byte limit"):
        calculate_expression("x", {"x": "1" * (MAX_NUMBER_UTF8_BYTES + 1)})


def test_expression_size_and_depth_limits_are_enforced() -> None:
    with pytest.raises(AICalculatorError, match="byte limit"):
        calculate_expression("1" + " " * MAX_EXPRESSION_UTF8_BYTES)
    deep = "1"
    for _ in range(MAX_AST_DEPTH + 2):
        deep = f"({deep} + 1)"
    with pytest.raises(AICalculatorError, match="depth limit"):
        calculate_expression(deep)


def test_result_bit_limit_is_enforced() -> None:
    large = 1 << MAX_RESULT_BITS

    with pytest.raises(AICalculatorError, match="bit limit"):
        calculate_expression("x", {"x": large})


@pytest.mark.parametrize("places", [-1, MAX_DECIMAL_PLACES + 1, True, 1.5])
def test_decimal_place_bounds_are_enforced(places) -> None:
    with pytest.raises(AICalculatorError, match="decimal_places"):
        calculate_expression("1 / 3", decimal_places=places)


def test_expression_tampering_is_rejected() -> None:
    receipt = calculate_expression("2 + 2")
    receipt["expression"] = "2 + 3"

    with pytest.raises(AICalculatorError, match="semantically inconsistent"):
        validate_calculation_receipt(receipt)


def test_result_tampering_after_rehash_is_rejected() -> None:
    receipt = calculate_expression("2 + 2")
    receipt["exact_result"]["numerator"] = "5"
    rehash(receipt)

    with pytest.raises(AICalculatorError, match="semantically inconsistent"):
        validate_calculation_receipt(receipt)


def test_operation_tampering_after_rehash_is_rejected() -> None:
    receipt = calculate_expression("2 + 2")
    receipt["operation_ids"] = ["MULTIPLY"]
    rehash(receipt)

    with pytest.raises(AICalculatorError, match="semantically inconsistent"):
        validate_calculation_receipt(receipt)


def test_premise_acceptance_and_authority_tampering_are_rejected() -> None:
    for field, value in (
        ("premise_status", "VALIDATED"),
        ("accepted", True),
        ("write_authority", "MODEL"),
    ):
        receipt = calculate_expression("2 + 2")
        receipt[field] = value
        rehash(receipt)
        with pytest.raises(AICalculatorError, match="semantically inconsistent"):
            validate_calculation_receipt(receipt)


def test_variable_tampering_after_rehash_is_rejected() -> None:
    receipt = calculate_expression("x + 1", {"x": 2})
    receipt["variables"]["x"]["numerator"] = "3"
    receipt["variables_hash"] = canonical_hash(receipt["variables"])
    rehash(receipt)

    with pytest.raises(AICalculatorError, match="semantically inconsistent"):
        validate_calculation_receipt(receipt)


def test_schema_and_hash_fail_closed() -> None:
    receipt = calculate_expression("2 + 2")
    receipt["extra"] = True
    with pytest.raises(AICalculatorError, match="fields do not match"):
        validate_calculation_receipt(receipt)

    receipt = calculate_expression("2 + 2")
    receipt["receipt_hash"] = "0" * 64
    with pytest.raises(AICalculatorError, match="hash mismatch"):
        validate_calculation_receipt(receipt)


def test_cyclic_and_nonfinite_receipts_fail_closed_in_calculator_domain() -> None:
    receipt = calculate_expression("2 + 2")
    receipt["cycle"] = receipt
    with pytest.raises(AICalculatorError, match="cycles"):
        validate_calculation_receipt(receipt)

    receipt = calculate_expression("2 + 2")
    receipt["decimal_places"] = float("inf")
    with pytest.raises(AICalculatorError, match="finite"):
        validate_calculation_receipt(receipt)