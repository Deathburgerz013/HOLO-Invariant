"""Exact, receipt-bound arithmetic for AI and human verification.

The calculator safely evaluates a deliberately small arithmetic language. It
does not execute Python, validate the truth of premises, accept conclusions,
or grant write authority.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from collections.abc import Mapping
from decimal import Decimal, DecimalException, localcontext
from fractions import Fraction
from typing import Any


AI_CALCULATION_TYPE = "holo_ai_calculation_receipt"
AI_CALCULATION_VERSION = 1
MAX_EXPRESSION_UTF8_BYTES = 4_096
MAX_NUMBER_UTF8_BYTES = 4_096
MAX_JSON_TEXT_UTF8_BYTES = 16_384
MAX_JSON_DEPTH = 12
MAX_JSON_ITEMS = 10_000
MAX_AST_NODES = 512
MAX_AST_DEPTH = 32
MAX_VARIABLES = 256
MAX_NAME_LENGTH = 128
MAX_RESULT_BITS = 8_192
MAX_EXPONENT_ABS = 1_024
MAX_DECIMAL_PLACES = 256

_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_NUMBER_PATTERN = re.compile(
    r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z"
)
_FRACTION_PATTERN = re.compile(
    r"([+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)"
    r"(?:/([+-]?(?:0|[1-9][0-9]*)))?\Z"
)


class AICalculatorError(ValueError):
    """Raised when an expression, variable, result, or receipt fails closed."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise AICalculatorError("value could not be canonicalized") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256(value: Any, field: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AICalculatorError(f"{field} must be 64 lowercase hex characters")
    return value


def _validate_closed_json(value: Any, field: str) -> None:
    active: set[int] = set()
    count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_JSON_ITEMS:
            raise AICalculatorError(f"{field} exceeds the JSON item limit")
        if depth > MAX_JSON_DEPTH:
            raise AICalculatorError(f"{field} exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise AICalculatorError(f"{field} numbers must be finite")
            return
        if type(item) is str:
            try:
                encoded = item.encode("utf-8")
            except UnicodeError as exc:
                raise AICalculatorError(f"{field} strings must be valid UTF-8") from exc
            if len(encoded) > MAX_JSON_TEXT_UTF8_BYTES:
                raise AICalculatorError(f"{field} string exceeds the UTF-8 byte limit")
            return
        if type(item) not in {dict, list}:
            raise AICalculatorError(f"{field} must contain only plain JSON values")
        identity = id(item)
        if identity in active:
            raise AICalculatorError(f"{field} must not contain cycles")
        active.add(identity)
        try:
            children = item.values() if type(item) is dict else item
            if type(item) is dict and any(type(key) is not str for key in item):
                raise AICalculatorError(f"{field} object keys must be plain strings")
            for child in children:
                visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _plain_object(value: Any, field: str, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise AICalculatorError(f"{field} must be a plain object")
    if set(value) != expected:
        raise AICalculatorError(f"{field} fields do not match the versioned schema")
    return value


def _expression_text(value: Any) -> str:
    if type(value) is not str or not value.strip():
        raise AICalculatorError("expression must be a nonempty plain string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise AICalculatorError("expression must be valid UTF-8") from exc
    if len(encoded) > MAX_EXPRESSION_UTF8_BYTES:
        raise AICalculatorError("expression exceeds the UTF-8 byte limit")
    return value


def _parse_fraction(value: Any, field: str) -> Fraction:
    if type(value) is int:
        result = Fraction(value)
    elif type(value) is str:
        try:
            encoded = value.encode("utf-8")
        except UnicodeError as exc:
            raise AICalculatorError(f"{field} must be valid UTF-8") from exc
        if len(encoded) > MAX_NUMBER_UTF8_BYTES:
            raise AICalculatorError(f"{field} exceeds the numeric byte limit")
        match = _FRACTION_PATTERN.fullmatch(value)
        if match is None:
            raise AICalculatorError(
                f"{field} must be an integer, decimal, or fraction string"
            )
        numerator, denominator = match.groups()
        try:
            result = Fraction(numerator)
            if denominator is not None:
                denominator_value = int(denominator)
                if denominator_value == 0:
                    raise AICalculatorError(f"{field} denominator cannot be zero")
                result /= denominator_value
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            raise AICalculatorError(f"{field} is not a valid exact number") from exc
    else:
        raise AICalculatorError(
            f"{field} must be an integer, decimal, or fraction string"
        )
    return _bounded(result, field)


def _bounded(value: Fraction, field: str = "result") -> Fraction:
    if (
        value.numerator.bit_length() > MAX_RESULT_BITS
        or value.denominator.bit_length() > MAX_RESULT_BITS
    ):
        raise AICalculatorError(f"{field} exceeds the exact-result bit limit")
    return value


def _normalize_variables(variables: Mapping[str, Any]) -> tuple[dict[str, Fraction], dict[str, dict[str, str]]]:
    if type(variables) is not dict:
        raise AICalculatorError("variables must be a plain object")
    if len(variables) > MAX_VARIABLES:
        raise AICalculatorError("variables exceed the item limit")
    parsed: dict[str, Fraction] = {}
    normalized: dict[str, dict[str, str]] = {}
    for name, raw_value in variables.items():
        if (
            type(name) is not str
            or len(name) > MAX_NAME_LENGTH
            or _NAME_PATTERN.fullmatch(name) is None
        ):
            raise AICalculatorError("variable names must be bounded Python identifiers")
        value = _parse_fraction(raw_value, f"variable {name!r}")
        parsed[name] = value
        normalized[name] = {
            "numerator": str(value.numerator),
            "denominator": str(value.denominator),
        }
    return parsed, normalized


def _validate_tree(tree: ast.AST) -> None:
    count = 0

    def visit(node: ast.AST, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_AST_NODES:
            raise AICalculatorError("expression exceeds the AST node limit")
        if depth > MAX_AST_DEPTH:
            raise AICalculatorError("expression exceeds the AST depth limit")
        allowed = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Name,
            ast.Load,
            ast.Constant,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.FloorDiv,
            ast.Mod,
            ast.Pow,
            ast.UAdd,
            ast.USub,
        )
        if not isinstance(node, allowed):
            raise AICalculatorError(
                f"expression contains forbidden syntax: {type(node).__name__}"
            )
        for child in ast.iter_child_nodes(node):
            visit(child, depth + 1)

    visit(tree, 0)


def _literal_fraction(expression: str, node: ast.Constant) -> Fraction:
    if type(node.value) not in {int, float}:
        raise AICalculatorError("only numeric literals are allowed")
    segment = ast.get_source_segment(expression, node)
    if segment is None or _NUMBER_PATTERN.fullmatch(segment) is None:
        raise AICalculatorError("numeric literal is not in the allowed format")
    try:
        return _bounded(Fraction(segment), "numeric literal")
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise AICalculatorError("numeric literal is invalid") from exc


def _evaluate(
    expression: str,
    node: ast.AST,
    variables: dict[str, Fraction],
    operations: list[str],
) -> Fraction:
    if isinstance(node, ast.Expression):
        return _evaluate(expression, node.body, variables, operations)
    if isinstance(node, ast.Constant):
        return _literal_fraction(expression, node)
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise AICalculatorError(f"unknown variable: {node.id}")
        return variables[node.id]
    if isinstance(node, ast.UnaryOp):
        value = _evaluate(expression, node.operand, variables, operations)
        if isinstance(node.op, ast.UAdd):
            operations.append("UNARY_PLUS")
            return value
        if isinstance(node.op, ast.USub):
            operations.append("UNARY_MINUS")
            return _bounded(-value)
    if isinstance(node, ast.BinOp):
        left = _evaluate(expression, node.left, variables, operations)
        right = _evaluate(expression, node.right, variables, operations)
        if isinstance(node.op, ast.Add):
            operations.append("ADD")
            return _bounded(left + right)
        if isinstance(node.op, ast.Sub):
            operations.append("SUBTRACT")
            return _bounded(left - right)
        if isinstance(node.op, ast.Mult):
            operations.append("MULTIPLY")
            return _bounded(left * right)
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise AICalculatorError("division by zero")
            operations.append("DIVIDE")
            return _bounded(left / right)
        if isinstance(node.op, ast.FloorDiv):
            if right == 0:
                raise AICalculatorError("floor division by zero")
            operations.append("FLOOR_DIVIDE")
            return Fraction(left // right)
        if isinstance(node.op, ast.Mod):
            if right == 0:
                raise AICalculatorError("modulo by zero")
            operations.append("MODULO")
            return _bounded(left % right)
        if isinstance(node.op, ast.Pow):
            if right.denominator != 1:
                raise AICalculatorError("exponent must be an exact integer")
            exponent = right.numerator
            if abs(exponent) > MAX_EXPONENT_ABS:
                raise AICalculatorError("exponent exceeds the absolute limit")
            if left == 0 and exponent < 0:
                raise AICalculatorError("zero cannot have a negative exponent")
            operations.append("POWER")
            return _bounded(left**exponent)
    raise AICalculatorError("expression contains unsupported arithmetic")


def _decimal_string(value: Fraction, places: int) -> str:
    try:
        with localcontext() as context:
            integer_digits = max(1, len(str(abs(value.numerator))))
            denominator_digits = max(1, len(str(value.denominator)))
            context.prec = max(32, integer_digits + denominator_digits + places + 8)
            decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
            quantum = Decimal(1).scaleb(-places)
            return format(decimal_value.quantize(quantum), "f")
    except DecimalException as exc:
        raise AICalculatorError("decimal approximation could not be produced") from exc


def _calculation_body(
    expression: Any, variables: Mapping[str, Any], decimal_places: Any
) -> dict[str, Any]:
    expression_text = _expression_text(expression)
    if type(decimal_places) is not int or not 0 <= decimal_places <= MAX_DECIMAL_PLACES:
        raise AICalculatorError(
            f"decimal_places must be an integer from 0 to {MAX_DECIMAL_PLACES}"
        )
    parsed_variables, normalized_variables = _normalize_variables(variables)
    try:
        tree = ast.parse(expression_text, mode="eval")
    except (SyntaxError, ValueError, MemoryError, RecursionError) as exc:
        raise AICalculatorError("expression is not valid arithmetic syntax") from exc
    _validate_tree(tree)
    operations: list[str] = []
    result = _evaluate(expression_text, tree, parsed_variables, operations)
    return {
        "type": AI_CALCULATION_TYPE,
        "version": AI_CALCULATION_VERSION,
        "expression": expression_text,
        "expression_sha256": hashlib.sha256(expression_text.encode("utf-8")).hexdigest(),
        "normalized_ast": ast.dump(tree, annotate_fields=True, include_attributes=False),
        "variables": normalized_variables,
        "variables_hash": _digest(normalized_variables),
        "operation_ids": operations,
        "exact_result": {
            "numerator": str(result.numerator),
            "denominator": str(result.denominator),
        },
        "decimal_places": decimal_places,
        "decimal_approximation": _decimal_string(result, decimal_places),
        "result_kind": "EXACT_RATIONAL",
        "premise_status": "NOT_VALIDATED",
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This receipt verifies bounded arithmetic for supplied inputs only. "
            "It does not prove that the inputs or premises are true, accept a "
            "conclusion, execute arbitrary code, or grant authority."
        ),
    }


def calculate_expression(
    expression: str,
    variables: Mapping[str, Any] | None = None,
    *,
    decimal_places: int = 12,
) -> dict[str, Any]:
    """Safely evaluate exact arithmetic and return a deterministic receipt."""
    body = _calculation_body(expression, {} if variables is None else variables, decimal_places)
    return {**body, "receipt_hash": _digest(body)}


def validate_calculation_receipt(receipt: Mapping[str, Any]) -> None:
    """Fail closed and recompute a stored calculation receipt."""
    _validate_closed_json(receipt, "calculation receipt")
    root = _plain_object(
        receipt,
        "calculation receipt",
        {
            "type",
            "version",
            "expression",
            "expression_sha256",
            "normalized_ast",
            "variables",
            "variables_hash",
            "operation_ids",
            "exact_result",
            "decimal_places",
            "decimal_approximation",
            "result_kind",
            "premise_status",
            "accepted",
            "write_authority",
            "interpretation_notice",
            "receipt_hash",
        },
    )
    if root["type"] != AI_CALCULATION_TYPE:
        raise AICalculatorError("calculation receipt type is invalid")
    if type(root["version"]) is not int or root["version"] != AI_CALCULATION_VERSION:
        raise AICalculatorError("calculation receipt version is invalid")
    _sha256(root["expression_sha256"], "expression_sha256")
    _sha256(root["variables_hash"], "variables_hash")
    _sha256(root["receipt_hash"], "receipt_hash")
    if type(root["variables"]) is not dict:
        raise AICalculatorError("receipt variables must be a plain object")
    reconstructed_variables: dict[str, str] = {}
    for name, pair_value in root["variables"].items():
        pair = _plain_object(
            pair_value,
            f"receipt variable {name!r}",
            {"numerator", "denominator"},
        )
        numerator = _parse_fraction(pair["numerator"], f"receipt variable {name!r} numerator")
        denominator = _parse_fraction(
            pair["denominator"], f"receipt variable {name!r} denominator"
        )
        if numerator.denominator != 1 or denominator.denominator != 1 or denominator == 0:
            raise AICalculatorError("receipt variable rational components are invalid")
        reconstructed_variables[name] = f"{numerator.numerator}/{denominator.numerator}"
    expected_body = _calculation_body(
        root["expression"], reconstructed_variables, root["decimal_places"]
    )
    actual_body = dict(root)
    receipt_hash = actual_body.pop("receipt_hash")
    if actual_body != expected_body:
        raise AICalculatorError("calculation receipt is semantically inconsistent")
    if _digest(actual_body) != receipt_hash:
        raise AICalculatorError("calculation receipt hash mismatch")