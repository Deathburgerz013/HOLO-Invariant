"""PARTIAL declared-reference experiment; no natural-language identity inference."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from holosim.bounded_contributor_attribution import build_bounded_contributor_attribution
from holosim.canonical import canonical_bytes, stable_hash

MAX_ITEMS = 256
MAX_TEXT = 256


class ReferenceHandoffError(ValueError):
    """Malformed input or a receipt not bound to the original inputs."""


def _text(value: Any) -> str:
    if type(value) is not str or not value.strip() or len(value) > MAX_TEXT:
        raise ReferenceHandoffError("expected bounded nonempty text")
    return value


def _fields(value: Any, fields: set[str]) -> None:
    if type(value) is not dict or set(value) != fields:
        raise ReferenceHandoffError("fields mismatch")


def _list(value: Any) -> list:
    if type(value) is not list or len(value) > MAX_ITEMS:
        raise ReferenceHandoffError("expected bounded list")
    return value


def _registry(registry: Any) -> list[dict]:
    result = []
    seen = set()
    for entity in _list(registry):
        _fields(entity, {"entity_id", "kind", "scope", "names"})
        eid = _text(entity["entity_id"])
        if eid in seen:
            raise ReferenceHandoffError("duplicate entity_id")
        seen.add(eid)
        names = [_text(name) for name in _list(entity["names"])]
        if not names or len(names) != len(set(names)):
            raise ReferenceHandoffError("empty or duplicate names")
        result.append({"entity_id": eid, "kind": _text(entity["kind"]),
                       "scope": _text(entity["scope"]), "names": sorted(names)})
    return sorted(result, key=lambda e: e["entity_id"])


def _request(request: Any) -> dict:
    _fields(request, {"name", "context", "entity_id"})
    context = request["context"]
    if type(context) is not dict or not set(context) <= {"kind", "scope"}:
        raise ReferenceHandoffError("invalid context")
    return {"name": _text(request["name"]),
            "context": {key: _text(value) for key, value in context.items()},
            "entity_id": None if request["entity_id"] is None else _text(request["entity_id"])}


def _resolve(registry: list[dict], request: dict) -> dict:
    candidates = [e["entity_id"] for e in registry
                  if request["name"] in e["names"]
                  and all(e[key] == value for key, value in request["context"].items())]
    eid = request["entity_id"]
    if eid is not None:
        status = "RESOLVED" if eid in candidates else "CONFLICT"
        selected = eid if status == "RESOLVED" else None
    else:
        status = "RESOLVED" if len(candidates) == 1 else "AMBIGUOUS" if candidates else "UNAVAILABLE"
        selected = candidates[0] if status == "RESOLVED" else None
    return {"request": deepcopy(request), "candidate_ids": candidates,
            "status": status, "entity_id": selected}


def evaluate_reference_handoff(*, registry: list, requests: list,
                               contributions: list) -> dict:
    """Resolve exact declared labels and round-trip explicit bindings.

    A caller-owned registry is an assumption, not authenticated identity.
    Contributions bind their declared entity directly, never via a display name.
    """
    entities = _registry(registry)
    checked_requests = [_request(r) for r in _list(requests)]
    ids = {e["entity_id"] for e in entities}
    attributions = []
    seen = set()
    for item in _list(contributions):
        _fields(item, {"contribution_id", "entity_id", "role", "text"})
        cid = _text(item["contribution_id"])
        eid = _text(item["entity_id"])
        if cid in seen or eid not in ids:
            raise ReferenceHandoffError("duplicate contribution or unknown entity")
        seen.add(cid)
        attributions.append(build_bounded_contributor_attribution(
            contributor_id=eid, role=_text(item["role"]),
            contribution={"contribution_id": cid, "text": _text(item["text"])}))
    resolutions = [_resolve(entities, r) for r in checked_requests]
    packet = {"registry": entities, "resolutions": resolutions, "attributions": attributions}
    encoded = canonical_bytes(packet)
    recovered = json.loads(encoded)
    body = {"type": "reference_ambiguity_handoff", "version": 1,
            "registry_hash": stable_hash(entities), "packet": packet,
            "checkpoint_sha256": stable_hash(packet),
            "recovered_packet": recovered,
            "recovery_equal": canonical_bytes(recovered) == encoded,
            "accepted": False, "truth_claimed": False,
            "write_authority": "NONE", "execution_authority": "NONE",
            "interpretation_notice": "Exact declared references only; no authentication, approval, selfhood, or free-text understanding."}
    return {**body, "receipt_hash": stable_hash(body)}


def verify_reference_handoff(receipt: dict, *, registry: list, requests: list,
                             contributions: list) -> bool:
    """Rerun from independently supplied originals, not receipt-owned inputs."""
    expected = evaluate_reference_handoff(registry=registry, requests=requests,
                                          contributions=contributions)
    try:
        equal = canonical_bytes(receipt) == canonical_bytes(expected)
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise ReferenceHandoffError("invalid receipt") from exc
    if not equal:
        raise ReferenceHandoffError("receipt does not match original inputs")
    return True


def demo_inputs() -> dict:
    return {"registry": [
        {"entity_id": "person:canyon-brock-haney", "kind": "person",
         "scope": "project:holo", "names": ["Canyon", "Canyon Brock Haney"]},
        {"entity_id": "place:grand-canyon", "kind": "place",
         "scope": "geography:example", "names": ["Canyon", "Grand Canyon"]}],
        "requests": [
            {"name": "Canyon", "context": {}, "entity_id": None},
            {"name": "Canyon", "context": {"kind": "person"}, "entity_id": None},
            {"name": "Canyon", "context": {"kind": "place"}, "entity_id": None},
            {"name": "Canyon", "context": {"kind": "place"}, "entity_id": "person:canyon-brock-haney"}],
        "contributions": [{"contribution_id": "observation:reference-ambiguity",
                           "entity_id": "person:canyon-brock-haney", "role": "problem framing",
                           "text": "A shared name can refer to different entities."}]}


def main() -> None:
    receipt = evaluate_reference_handoff(**demo_inputs())
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
