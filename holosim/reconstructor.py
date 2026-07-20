"""Bounded, read-only reconstruction manifests for Holo/Sim.

A reconstruction does not claim memory, truth, acceptance, or authority. It
compares accountable observations relative to an explicit reference and emits
the smallest closed manifest needed to expose correspondence, difference, and
unresolved state.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

RECONSTRUCTION_TYPE = "holo_reconstruction_manifest"
RECONSTRUCTION_VERSION = 1
MAX_ITEMS = 10_000
MAX_JSON_DEPTH = 8


class ReconstructionError(ValueError):
    """Raised when reconstruction inputs or manifests are malformed."""


def _closed_json(value: Any) -> None:
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > MAX_JSON_DEPTH:
            raise ReconstructionError("value exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int, str}:
            if type(item) is str:
                try:
                    item.encode("utf-8")
                except UnicodeError as exc:
                    raise ReconstructionError("strings must be valid UTF-8") from exc
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise ReconstructionError("numbers must be finite")
            return
        if type(item) not in {dict, list}:
            raise ReconstructionError("values must contain only plain JSON types")
        identity = id(item)
        if identity in active:
            raise ReconstructionError("values must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise ReconstructionError("object keys must be strings")
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
        raise ReconstructionError("manifest could not be canonicalized") from exc
    return hashlib.sha256(encoded).hexdigest()


def _require_text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ReconstructionError(f"{field} must be a nonempty plain string")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ReconstructionError(f"{field} must be valid UTF-8") from exc
    return value


def _normalize_items(items: Sequence[Mapping[str, Any]], field: str) -> list[dict[str, Any]]:
    if type(items) not in {list, tuple}:
        raise ReconstructionError(f"{field} must be a list or tuple")
    if len(items) > MAX_ITEMS:
        raise ReconstructionError(f"{field} exceeds maximum item count")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if type(item) is not dict:
            raise ReconstructionError(f"{field}[{index}] must be a plain dictionary")
        _closed_json(item)
        item_id = _require_text(item.get("id"), f"{field}[{index}].id")
        if item_id in seen:
            raise ReconstructionError(f"duplicate reconstruction item id: {item_id}")
        seen.add(item_id)
        normalized.append(dict(item))
    return normalized


def build_reconstruction_manifest(
    reference: str,
    prior_items: Sequence[Mapping[str, Any]],
    current_items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare explicit prior/current items and emit a read-only reconstruction.

    Items are matched only by explicit ``id``. The reconstructor does not infer
    semantic equivalence. Each item may contain arbitrary closed JSON evidence.
    """
    checked_reference = _require_text(reference, "reference")
    prior = _normalize_items(prior_items, "prior_items")
    current = _normalize_items(current_items, "current_items")
    prior_by_id = {item["id"]: item for item in prior}
    current_by_id = {item["id"]: item for item in current}

    prior_ids = set(prior_by_id)
    current_ids = set(current_by_id)
    shared_ids = sorted(prior_ids & current_ids)
    preserved: list[str] = []
    changed: list[dict[str, str]] = []

    for item_id in shared_ids:
        prior_hash = _hash(prior_by_id[item_id])
        current_hash = _hash(current_by_id[item_id])
        if prior_hash == current_hash:
            preserved.append(item_id)
        else:
            changed.append({
                "id": item_id,
                "prior_sha256": prior_hash,
                "current_sha256": current_hash,
            })

    missing = sorted(prior_ids - current_ids)
    added = sorted(current_ids - prior_ids)
    status = "RECONSTRUCTED" if not changed and not missing else "DIFFERENCE"

    body: dict[str, Any] = {
        "type": RECONSTRUCTION_TYPE,
        "version": RECONSTRUCTION_VERSION,
        "reference": checked_reference,
        "prior_count": len(prior),
        "current_count": len(current),
        "preserved_ids": preserved,
        "changed": changed,
        "missing_ids": missing,
        "added_ids": added,
        "status": status,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Reconstruction reports explicit correspondence and difference only. "
            "It does not establish truth, memory, acceptance, or authority."
        ),
    }
    return {**body, "reconstruction_hash": _hash(body)}


def validate_reconstruction_manifest(manifest: Mapping[str, Any]) -> bool:
    """Fail closed unless a reconstruction manifest is structurally self-consistent."""
    if type(manifest) is not dict:
        raise ReconstructionError("manifest must be a plain dictionary")
    _closed_json(manifest)
    expected = {
        "type", "version", "reference", "prior_count", "current_count",
        "preserved_ids", "changed", "missing_ids", "added_ids", "status",
        "accepted", "write_authority", "interpretation_notice",
        "reconstruction_hash",
    }
    if set(manifest) != expected:
        raise ReconstructionError("manifest fields do not match the versioned schema")
    if manifest["type"] != RECONSTRUCTION_TYPE or manifest["version"] != RECONSTRUCTION_VERSION:
        raise ReconstructionError("manifest type or version is invalid")
    _require_text(manifest["reference"], "reference")
    for field in ("prior_count", "current_count"):
        if type(manifest[field]) is not int or not 0 <= manifest[field] <= MAX_ITEMS:
            raise ReconstructionError(f"{field} is invalid")
    if manifest["accepted"] is not False or manifest["write_authority"] != "NONE":
        raise ReconstructionError("reconstruction cannot grant acceptance or write authority")
    if type(manifest["interpretation_notice"]) is not str:
        raise ReconstructionError("interpretation_notice must be a string")
    for field in ("preserved_ids", "missing_ids", "added_ids"):
        values = manifest[field]
        if type(values) is not list or any(type(value) is not str or not value for value in values):
            raise ReconstructionError(f"{field} must be a list of nonempty strings")
        if values != sorted(set(values)):
            raise ReconstructionError(f"{field} must be sorted and unique")
    changed = manifest["changed"]
    if type(changed) is not list:
        raise ReconstructionError("changed must be a list")
    changed_ids: list[str] = []
    for entry in changed:
        if type(entry) is not dict or set(entry) != {"id", "prior_sha256", "current_sha256"}:
            raise ReconstructionError("changed entry fields are invalid")
        changed_ids.append(_require_text(entry["id"], "changed.id"))
        for field in ("prior_sha256", "current_sha256"):
            if type(entry[field]) is not str or not re.fullmatch(r"[0-9a-f]{64}", entry[field]):
                raise ReconstructionError(f"changed.{field} must be a SHA-256 hex digest")
        if entry["prior_sha256"] == entry["current_sha256"]:
            raise ReconstructionError("changed entry hashes must differ")
    if changed_ids != sorted(set(changed_ids)):
        raise ReconstructionError("changed ids must be sorted and unique")
    all_groups = [set(manifest["preserved_ids"]), set(changed_ids), set(manifest["missing_ids"]), set(manifest["added_ids"])]
    for index, left in enumerate(all_groups):
        for right in all_groups[index + 1:]:
            if left & right:
                raise ReconstructionError("reconstruction id classifications must be disjoint")
    if manifest["prior_count"] != len(manifest["preserved_ids"]) + len(changed) + len(manifest["missing_ids"]):
        raise ReconstructionError("prior_count is inconsistent with classifications")
    if manifest["current_count"] != len(manifest["preserved_ids"]) + len(changed) + len(manifest["added_ids"]):
        raise ReconstructionError("current_count is inconsistent with classifications")
    expected_status = "RECONSTRUCTED" if not changed and not manifest["missing_ids"] else "DIFFERENCE"
    if manifest["status"] != expected_status:
        raise ReconstructionError("status is inconsistent with classifications")
    receipt_hash = manifest["reconstruction_hash"]
    if type(receipt_hash) is not str or not re.fullmatch(r"[0-9a-f]{64}", receipt_hash):
        raise ReconstructionError("reconstruction_hash must be a SHA-256 hex digest")
    body = dict(manifest)
    body.pop("reconstruction_hash")
    if _hash(body) != receipt_hash:
        raise ReconstructionError("reconstruction hash mismatch")
    return True
