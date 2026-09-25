"""Snapshot-scoped route constraint checks without permission or truth claims.

Observed values and route requirements are caller-supplied. A valid snapshot
establishes structure and identity, not the truth or sufficiency of a sensor.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.environment_snapshot import verify_snapshot


RECEIPT_TYPE = "environment_route_gate_receipt"
RECEIPT_VERSION = 1


class RouteGateError(ValueError):
    """Raised when route or snapshot inputs cannot support a scoped check."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RouteGateError(f"{name} must be a nonempty string")
    return value


def _requirements(value: Any) -> dict[str, bool]:
    if not isinstance(value, Mapping) or not value:
        raise RouteGateError("required_observations must be a nonempty mapping")
    result: dict[str, bool] = {}
    for key, expected in value.items():
        name = _text(key, "required_observations key")
        if type(expected) is not bool:
            raise RouteGateError("required_observations values must be booleans")
        result[name] = expected
    return result


def _marked_unknown(snapshot: Mapping[str, Any], field: str) -> bool:
    marked = False
    for category in ("unknown", "missing", "assumptions", "uncertainty"):
        for item in snapshot[category]:
            if category in ("unknown", "missing") and not (
                isinstance(item, Mapping)
                and any(
                    isinstance(item.get(key), str) and item[key].strip()
                    for key in ("field", "signal")
                )
            ):
                raise RouteGateError(
                    f"{category} marker must identify a field or signal"
                )
            if isinstance(item, Mapping) and (
                item.get("field") == field or item.get("signal") == field
            ):
                marked = True
    return marked


def evaluate_route_gate(
    *,
    snapshot: Mapping[str, Any],
    route_id: str,
    required_observations: Mapping[str, bool],
    requirement_basis_ref: str,
) -> dict[str, Any]:
    """Compare one declared route with one structurally valid snapshot.

    A conflict closes only the snapshot-scoped candidate comparison. Later
    snapshots, evidence corrections, or revised requirements demand recheck.
    Compatibility does not grant permission or demonstrate route feasibility.
    """
    route = _text(route_id, "route_id")
    requirements = _requirements(required_observations)
    basis = _text(requirement_basis_ref, "requirement_basis_ref")
    if not isinstance(snapshot, Mapping):
        raise RouteGateError("snapshot must be a mapping")
    verification = verify_snapshot(snapshot)
    if not verification["valid"]:
        raise RouteGateError("snapshot is invalid: " + "; ".join(verification["violations"]))

    observed = snapshot["observed"]
    conflicts: list[str] = []
    unresolved: list[str] = []
    matching: list[str] = []
    for field, expected in sorted(requirements.items()):
        if _marked_unknown(snapshot, field) or field not in observed:
            unresolved.append(field)
        elif type(observed[field]) is not bool:
            raise RouteGateError(f"observed {field} must be a boolean")
        elif observed[field] != expected:
            conflicts.append(field)
        else:
            matching.append(field)

    status = (
        "OBSERVED_CONFLICT" if conflicts
        else "UNRESOLVED" if unresolved
        else "OBSERVED_COMPATIBLE"
    )
    try:
        requirements_hash = stable_hash({
            "required_observations": requirements,
            "requirement_basis_ref": basis,
        })
        dependencies = sorted(set(
            [snapshot["snapshot_id"], requirements_hash, *snapshot["evidence_sha256"]]
        ))
        payload = {
            "type": RECEIPT_TYPE,
            "version": RECEIPT_VERSION,
            "route_id": route,
            "requirement_basis_ref": basis,
            "required_observations": deepcopy(requirements),
            "requirements_hash": requirements_hash,
            "environment_id": snapshot["environment_id"],
            "episode_id": snapshot["episode_id"],
            "check_id": snapshot["check_id"],
            "observed_at": snapshot["observed_at"],
            "snapshot_id": snapshot["snapshot_id"],
            "evidence_receipt_hashes": dependencies,
            "status": status,
            "conflicting_fields": conflicts,
            "unresolved_fields": unresolved,
            "matching_fields": matching,
            "observation_truth_verified": False,
            "route_feasibility_verified": False,
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
            "interpretation_notice": (
                "Status compares declared route requirements with one recorded "
                "snapshot. Hashes identify inputs, not observation truth. "
                "Recheck after a later snapshot, evidence correction, or "
                "changed route requirements. No permission is granted."
            ),
        }
        return {**payload, "receipt_hash": stable_hash(payload)}
    except CanonicalValueError as exc:
        raise RouteGateError(str(exc)) from exc


def verify_route_gate_receipt(
    receipt: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """Replay a receipt against its supplied source snapshot, without truth claims."""
    violations: list[str] = []
    expected_hash = None
    actual_hash = receipt.get("receipt_hash") if isinstance(receipt, Mapping) else None
    try:
        if not isinstance(receipt, Mapping):
            raise RouteGateError("receipt must be a mapping")
        replay = evaluate_route_gate(
            snapshot=snapshot,
            route_id=receipt.get("route_id"),
            required_observations=receipt.get("required_observations"),
            requirement_basis_ref=receipt.get("requirement_basis_ref"),
        )
        expected_hash = replay["receipt_hash"]
        if set(receipt) != set(replay):
            violations.append("receipt fields do not match snapshot replay")
        for field, value in replay.items():
            if field in receipt and receipt[field] != value:
                violations.append(f"{field} does not match snapshot replay")
    except (RouteGateError, CanonicalValueError, TypeError) as exc:
        violations.append(str(exc))
    return {
        "valid": not violations,
        "receipt_hash": actual_hash,
        "expected_receipt_hash": expected_hash,
        "violations": violations,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Replay checks the receipt against a supplied snapshot. "
            "It does not verify the observation's truth or grant permission."
        ),
    }
