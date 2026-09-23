from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import stable_hash


def _validate_report(
    report: Mapping[str, Any] | None,
    name: str,
) -> dict[str, Any] | None:
    if report is None:
        return None

    if type(report) is not dict:
        raise ValueError(f"{name} must be a plain dictionary")

    if not report:
        raise ValueError(f"{name} must not be empty")

    if type(report.get("type")) is not str or not report["type"].strip():
        raise ValueError(f"{name} must declare a type")

    if "version" not in report:
        raise ValueError(f"{name} must declare a version")

    return deepcopy(report)


def build_status_report(
    *,
    invariant_audit: Mapping[str, Any] | None,
    spine_validation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Aggregate existing verified reports without upgrading their evidence."""

    audit = _validate_report(invariant_audit, "invariant_audit")
    spine = _validate_report(spine_validation, "spine_validation")

    body = {
        "type": "holo_status_report",
        "version": 1,
        "invariant_audit": audit,
        "spine_validation": spine,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {
        **body,
        "report_hash": stable_hash(body),
    }
def verify_status_report(report: Mapping[str, Any]) -> bool:
    """Verify that a status report's hash matches its immutable body."""

    if type(report) is not dict:
        raise ValueError("report must be a plain dictionary")

    if "report_hash" not in report:
        raise ValueError("report must contain report_hash")

    supplied_hash = report["report_hash"]

    if type(supplied_hash) is not str:
        raise ValueError("report_hash must be a string")

    body = {
        key: value
        for key, value in report.items()
        if key != "report_hash"
    }

    if stable_hash(body) != supplied_hash:
        raise ValueError("status report hash mismatch")

    return True