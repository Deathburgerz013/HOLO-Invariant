"""Bounded, read-only reproduction and compression checks.

A reproduction check asks whether a smaller candidate substrate reproduces the
same explicit observed outcomes as a baseline. It does not infer semantic
similarity, truth, acceptance, authority, or global obsolescence.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

REPRODUCTION_TYPE = "holo_reproduction_check"
REPRODUCTION_VERSION = 1
MAX_ITEMS = 10_000
MAX_JSON_DEPTH = 8


class ReproductionError(ValueError):
    """Raised when reproduction inputs are malformed."""


def _closed_json(value: Any) -> None:
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > MAX_JSON_DEPTH:
            raise ReproductionError("value exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int, str}:
            if type(item) is str:
                try:
                    item.encode("utf-8")
                except UnicodeError as exc:
                    raise ReproductionError("strings must be valid UTF-8") from exc
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise ReproductionError("numbers must be finite")
            return
        if type(item) not in {dict, list}:
            raise ReproductionError("values must contain only plain JSON types")
        identity = id(item)
        if identity in active:
            raise ReproductionError("values must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise ReproductionError("object keys must be strings")
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _hash(value: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise ReproductionError("value could not be canonicalized") from exc
    return hashlib.sha256(encoded).hexdigest()


def _require_text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ReproductionError(f"{field} must be a nonempty plain string")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ReproductionError(f"{field} must be valid UTF-8") from exc
    return value


def _normalize_items(items: Sequence[Mapping[str, Any]], field: str) -> list[dict[str, Any]]:
    if type(items) not in {list, tuple}:
        raise ReproductionError(f"{field} must be a list or tuple")
    if len(items) > MAX_ITEMS:
        raise ReproductionError(f"{field} exceeds maximum item count")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if type(item) is not dict:
            raise ReproductionError(f"{field}[{index}] must be a plain dictionary")
        _closed_json(item)
        item_id = _require_text(item.get("id"), f"{field}[{index}].id")
        if item_id in seen:
            raise ReproductionError(f"duplicate {field} id: {item_id}")
        seen.add(item_id)
        normalized.append(dict(item))
    return normalized


def build_reproduction_check(
    reference: str,
    baseline_substrate: Sequence[Mapping[str, Any]],
    candidate_substrate: Sequence[Mapping[str, Any]],
    baseline_outcomes: Sequence[Mapping[str, Any]],
    candidate_outcomes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare a candidate substrate against explicit baseline outcomes.

    Outcomes are matched only by explicit ``id`` and exact canonical content.
    A candidate is ``REPRODUCED`` only when every baseline outcome is present
    and unchanged. Removed substrate items are reported as unnecessary only for
    this observed reproduction; no global obsolescence claim is made.
    """
    checked_reference = _require_text(reference, "reference")
    baseline_s = _normalize_items(baseline_substrate, "baseline_substrate")
    candidate_s = _normalize_items(candidate_substrate, "candidate_substrate")
    baseline_o = _normalize_items(baseline_outcomes, "baseline_outcomes")
    candidate_o = _normalize_items(candidate_outcomes, "candidate_outcomes")

    baseline_s_ids = {item["id"] for item in baseline_s}
    candidate_s_ids = {item["id"] for item in candidate_s}
    baseline_by_id = {item["id"]: item for item in baseline_o}
    candidate_by_id = {item["id"]: item for item in candidate_o}

    preserved_outcomes: list[str] = []
    changed_outcomes: list[dict[str, str]] = []
    missing_outcomes: list[str] = []

    for outcome_id in sorted(baseline_by_id):
        baseline_item = baseline_by_id[outcome_id]
        candidate_item = candidate_by_id.get(outcome_id)
        if candidate_item is None:
            missing_outcomes.append(outcome_id)
            continue
        baseline_hash = _hash(baseline_item)
        candidate_hash = _hash(candidate_item)
        if baseline_hash == candidate_hash:
            preserved_outcomes.append(outcome_id)
        else:
            changed_outcomes.append(
                {
                    "id": outcome_id,
                    "baseline_sha256": baseline_hash,
                    "candidate_sha256": candidate_hash,
                }
            )

    added_outcomes = sorted(set(candidate_by_id) - set(baseline_by_id))
    removed_substrate = sorted(baseline_s_ids - candidate_s_ids)
    added_substrate = sorted(candidate_s_ids - baseline_s_ids)

    reproduced = not missing_outcomes and not changed_outcomes
    status = "REPRODUCED" if reproduced else "NOT_REPRODUCED"

    body: dict[str, Any] = {
        "type": REPRODUCTION_TYPE,
        "version": REPRODUCTION_VERSION,
        "reference": checked_reference,
        "status": status,
        "baseline_substrate_count": len(baseline_s),
        "candidate_substrate_count": len(candidate_s),
        "baseline_outcome_count": len(baseline_o),
        "candidate_outcome_count": len(candidate_o),
        "preserved_outcome_ids": preserved_outcomes,
        "changed_outcomes": changed_outcomes,
        "missing_outcome_ids": missing_outcomes,
        "added_outcome_ids": added_outcomes,
        "removed_substrate_ids": removed_substrate,
        "added_substrate_ids": added_substrate,
        "candidate_is_smaller": len(candidate_s) < len(baseline_s),
        "removed_substrate_not_required_for_observed_reproduction": (
            removed_substrate if reproduced else []
        ),
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "REPRODUCED means only that all explicit baseline outcomes were "
            "reproduced exactly for this supplied observation. Removed substrate "
            "items are not thereby globally obsolete, false, or useless."
        ),
    }
    return {**body, "reproduction_hash": _hash(body)}
