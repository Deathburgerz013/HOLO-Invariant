"""Deterministic identity for a bounded subset of Python callables."""

from __future__ import annotations

import hashlib
import inspect
import json
import marshal
import types
from typing import Any, Callable


IDENTITY_TYPE = "bounded_python_callable_identity"
IDENTITY_VERSION = 1


class BoundedPythonCallableIdentityError(ValueError):
    """Raised when a callable cannot be safely identified by this contract."""


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any, label: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise BoundedPythonCallableIdentityError(
            f"{label} must contain only canonical JSON values"
        ) from exc


def derive_python_callable_identity(
    function: Callable[..., Any],
) -> dict[str, Any]:
    """Derive identity for a plain, closure-free Python function.

    This contract intentionally rejects callable objects, builtins, bound
    methods, closures, and functions whose defaults cannot be represented as
    canonical JSON.
    """

    if not isinstance(function, types.FunctionType):
        raise BoundedPythonCallableIdentityError(
            "callable must be a plain Python function"
        )

    if inspect.ismethod(function):
        raise BoundedPythonCallableIdentityError(
            "bound methods are not supported"
        )

    if function.__closure__:
        raise BoundedPythonCallableIdentityError(
            "closures are not supported"
        )

    module = function.__module__
    qualname = function.__qualname__

    if type(module) is not str or not module.strip():
        raise BoundedPythonCallableIdentityError(
            "function module must be a nonempty plain string"
        )
    if type(qualname) is not str or not qualname.strip():
        raise BoundedPythonCallableIdentityError(
            "function qualname must be a nonempty plain string"
        )

    defaults = _canonical_json(
        list(function.__defaults__ or ()),
        "function defaults",
    )
    kwdefaults = _canonical_json(
        function.__kwdefaults__ or {},
        "function keyword defaults",
    )

    code = function.__code__

    # marshal gives us a deterministic representation of the complete code
    # object for the running Python implementation. We bind the interpreter
    # implementation/version because marshal is intentionally version-bound.
    marshalled_code = marshal.dumps(code)

    body = {
        "type": IDENTITY_TYPE,
        "version": IDENTITY_VERSION,
        "python_implementation": __import__("platform").python_implementation(),
        "python_version": __import__("platform").python_version(),
        "module": module,
        "qualname": qualname,
        "defaults": defaults,
        "kwdefaults": kwdefaults,
        "code_sha256": _hash_bytes(marshalled_code),
    }

    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    return {
        **body,
        "callable_identity": _hash_bytes(encoded),
    }


def verify_python_callable_identity(
    function: Callable[..., Any],
    identity: dict[str, Any],
) -> dict[str, Any]:
    """Re-derive callable identity and compare it with a supplied record."""

    violations: list[str] = []

    try:
        expected = derive_python_callable_identity(function)
    except BoundedPythonCallableIdentityError as exc:
        return {
            "valid": False,
            "expected_callable_identity": None,
            "observed_callable_identity": (
                identity.get("callable_identity")
                if isinstance(identity, dict)
                else None
            ),
            "violations": [str(exc)],
            "accepted": False,
            "write_authority": "NONE",
        }

    if not isinstance(identity, dict):
        violations.append("identity must be a dict")
        observed = None
    else:
        observed = identity.get("callable_identity")

        if set(identity) != set(expected):
            violations.append("identity fields do not match")

        for field, expected_value in expected.items():
            if identity.get(field) != expected_value:
                violations.append(f"{field} does not match")

    return {
        "valid": not violations,
        "expected_callable_identity": expected["callable_identity"],
        "observed_callable_identity": observed,
        "violations": violations,
        "accepted": False,
        "write_authority": "NONE",
    }