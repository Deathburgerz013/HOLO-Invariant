from copy import deepcopy

import pytest

from holosim.bounded_python_callable_identity import (
    BoundedPythonCallableIdentityError,
    derive_python_callable_identity,
    verify_python_callable_identity,
)


def observer(value, context):
    return value["value"] + context["offset"]


def same_shape_different_behavior(value, context):
    return value["value"] - context["offset"]


def with_default(value, context, scale=1):
    return value["value"] * scale


def test_same_function_has_stable_identity():
    first = derive_python_callable_identity(observer)
    second = derive_python_callable_identity(observer)

    assert first == second
    assert len(first["callable_identity"]) == 64
    assert len(first["code_sha256"]) == 64


def test_different_implementation_has_different_identity():
    first = derive_python_callable_identity(observer)
    second = derive_python_callable_identity(same_shape_different_behavior)

    assert first["callable_identity"] != second["callable_identity"]
    assert first["code_sha256"] != second["code_sha256"]


def test_identity_binds_module_and_qualname():
    identity = derive_python_callable_identity(observer)

    assert identity["module"] == __name__
    assert identity["qualname"].endswith("observer")


def test_default_values_are_bound():
    original = derive_python_callable_identity(with_default)

    def changed_default(value, context, scale=2):
        return value["value"] * scale

    changed = derive_python_callable_identity(changed_default)

    assert original["callable_identity"] != changed["callable_identity"]
    assert original["defaults"] == [1]
    assert changed["defaults"] == [2]


def test_valid_identity_replays_against_same_function():
    identity = derive_python_callable_identity(observer)
    result = verify_python_callable_identity(observer, identity)

    assert result["valid"] is True
    assert result["violations"] == []
    assert (
        result["expected_callable_identity"]
        == identity["callable_identity"]
    )


def test_identity_from_different_function_fails():
    identity = derive_python_callable_identity(observer)
    result = verify_python_callable_identity(
        same_shape_different_behavior,
        identity,
    )

    assert result["valid"] is False
    assert result["violations"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("module", "fabricated.module"),
        ("qualname", "fabricated"),
        ("defaults", ["fabricated"]),
        ("code_sha256", "0" * 64),
        ("callable_identity", "1" * 64),
    ],
)
def test_tampered_identity_fails(field, value):
    identity = derive_python_callable_identity(observer)
    forged = deepcopy(identity)
    forged[field] = value

    result = verify_python_callable_identity(observer, forged)

    assert result["valid"] is False


def test_added_field_fails():
    identity = derive_python_callable_identity(observer)
    identity["invented"] = True

    result = verify_python_callable_identity(observer, identity)

    assert result["valid"] is False


def test_lambda_without_closure_is_supported():
    function = lambda value, context: value["value"]
    identity = derive_python_callable_identity(function)

    assert identity["qualname"]
    assert len(identity["callable_identity"]) == 64


def test_closure_fails_closed():
    offset = 2

    def closed(value, context):
        return value["value"] + offset

    with pytest.raises(
        BoundedPythonCallableIdentityError,
        match="closures are not supported",
    ):
        derive_python_callable_identity(closed)


@pytest.mark.parametrize(
    "value",
    [
        len,
        object(),
        str.upper,
    ],
)
def test_unsupported_callable_forms_fail_closed(value):
    with pytest.raises(
        BoundedPythonCallableIdentityError,
        match="plain Python function",
    ):
        derive_python_callable_identity(value)


def test_non_json_default_fails_closed():
    marker = object()

    def invalid(value, context, default=marker):
        return value

    with pytest.raises(
        BoundedPythonCallableIdentityError,
        match="canonical JSON",
    ):
        derive_python_callable_identity(invalid)


def test_verification_grants_no_authority():
    identity = derive_python_callable_identity(observer)
    result = verify_python_callable_identity(observer, identity)

    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"