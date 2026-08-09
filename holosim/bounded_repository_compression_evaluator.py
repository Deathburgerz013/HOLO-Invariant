"""Bounded behavioral evaluator for proposed repository compression.

The evaluator compares reconstructed compression rounds with one unchanged
baseline over an explicitly declared finite observer/context scope.  It does
not infer universal equivalence, mutate repositories, approve promotion, or
grant truth, write, or execution authority.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Callable, Mapping

from holosim.canonical import CanonicalValueError, canonical_bytes, stable_hash


RECEIPT_TYPE = "bounded_repository_compression_receipt"
RECEIPT_VERSION = 1

EQUIVALENT = "EQUIVALENT"
DISTINCTION_LOST = "DISTINCTION_LOST"
UNKNOWN = "UNKNOWN"

NOT_SIZE_REDUCING = "NOT_SIZE_REDUCING"
EVALUATION_ERROR = "EVALUATION_ERROR"
EFFECT_RUNNER_REQUIRED = "EFFECT_RUNNER_REQUIRED"
EFFECT_BOUNDARY_UNVERIFIED = "EFFECT_BOUNDARY_UNVERIFIED"

MAX_ROUNDS = 64
MAX_OBSERVERS = 128
MAX_CONTEXTS = 128
MAX_CANONICAL_BYTES = 2_000_000

SCOPE_FIELDS = {
    "observer_family_id",
    "observer_family_hash",
    "context_set_id",
    "context_set_hash",
    "compression_id",
    "compression_hash",
    "reconstruction_id",
    "reconstruction_hash",
    "block_encoder_id",
    "block_encoder_hash",
    "representation_encoder_id",
    "representation_encoder_hash",
    "platform_id",
    "platform_hash",
    "effect_runner_id",
    "effect_runner_hash",
    "determinism",
}

EFFECT_RESULT_FIELDS = {
    "status",
    "value",
    "effects",
    "external_effects_blocked",
}

ROUND_FIELDS = {
    "round",
    "source_block_id",
    "compressed_representation_id",
    "reconstructed_block_id",
    "source_size_bytes",
    "representation_size_bytes",
    "size_reducing",
    "observation_vector",
}

OBSERVATION_FIELDS = {
    "observer_id",
    "context_id",
    "observation",
}

WITNESS_FIELDS = {
    "round",
    "observer_id",
    "context_id",
    "baseline_observation",
    "candidate_observation",
}

RECEIPT_BODY_FIELDS = {
    "type",
    "version",
    "scope",
    "round_bound",
    "baseline_block_id",
    "baseline_observation_vector",
    "rounds",
    "result",
    "reason",
    "mismatch_witness",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "interpretation_notice",
}

Observer = Callable[[Mapping[str, Any], Any], Any]
Transform = Callable[[Any], Any]
EffectRunner = Callable[..., Mapping[str, Any]]


class BoundedRepositoryCompressionError(ValueError):
    """Raised when evaluation input or a receipt violates its contract."""


class _EffectBoundaryUnknown(RuntimeError):
    """Raised internally when execution confinement is not established."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise BoundedRepositoryCompressionError(str(exc)) from exc


def _canonical_size(value: Any) -> int:
    try:
        size = len(canonical_bytes(value))
    except CanonicalValueError as exc:
        raise BoundedRepositoryCompressionError(str(exc)) from exc
    if size > MAX_CANONICAL_BYTES:
        raise BoundedRepositoryCompressionError(
            f"value cannot exceed {MAX_CANONICAL_BYTES} canonical bytes"
        )
    return size


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BoundedRepositoryCompressionError(
            f"{field} must be a non-empty string"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise BoundedRepositoryCompressionError(
            f"{field} must be lowercase SHA-256 hex"
        )
    return text


def _exact_fields(
    value: Any,
    fields: set[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BoundedRepositoryCompressionError(f"{label} must be an object")
    normalized = deepcopy(dict(value))
    missing = sorted(fields - set(normalized))
    extra = sorted(set(normalized) - fields)
    if missing:
        raise BoundedRepositoryCompressionError(
            f"{label} is missing fields: " + ", ".join(missing)
        )
    if extra:
        raise BoundedRepositoryCompressionError(
            f"{label} has unsupported fields: " + ", ".join(extra)
        )
    return normalized


def build_evaluation_scope(
    *,
    observer_family_id: str,
    observer_family: Any,
    context_set_id: str,
    context_set: Any,
    compression_id: str,
    compression_contract: Any,
    reconstruction_id: str,
    reconstruction_contract: Any,
    block_encoder_id: str,
    block_encoder_contract: Any,
    representation_encoder_id: str,
    representation_encoder_contract: Any,
    platform_id: str,
    platform_contract: Any,
    effect_runner_id: str,
    effect_runner_contract: Any,
    determinism: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the finite evaluation-scope identity used by a receipt."""
    normalized_determinism = deepcopy(dict(determinism))
    _hash(normalized_determinism)
    return {
        "observer_family_id": _required_text(
            observer_family_id, "observer_family_id"
        ),
        "observer_family_hash": _hash(observer_family),
        "context_set_id": _required_text(context_set_id, "context_set_id"),
        "context_set_hash": _hash(context_set),
        "compression_id": _required_text(compression_id, "compression_id"),
        "compression_hash": _hash(compression_contract),
        "reconstruction_id": _required_text(
            reconstruction_id, "reconstruction_id"
        ),
        "reconstruction_hash": _hash(reconstruction_contract),
        "block_encoder_id": _required_text(
            block_encoder_id, "block_encoder_id"
        ),
        "block_encoder_hash": _hash(block_encoder_contract),
        "representation_encoder_id": _required_text(
            representation_encoder_id, "representation_encoder_id"
        ),
        "representation_encoder_hash": _hash(
            representation_encoder_contract
        ),
        "platform_id": _required_text(platform_id, "platform_id"),
        "platform_hash": _hash(platform_contract),
        "effect_runner_id": _required_text(
            effect_runner_id, "effect_runner_id"
        ),
        "effect_runner_hash": _hash(effect_runner_contract),
        "determinism": normalized_determinism,
    }


def _validate_scope(scope: Any) -> dict[str, Any]:
    normalized = _exact_fields(scope, SCOPE_FIELDS, "scope")
    for field in SCOPE_FIELDS:
        if field.endswith("_hash"):
            _sha256(normalized[field], field)
        elif field != "determinism":
            _required_text(normalized[field], field)
    if not isinstance(normalized["determinism"], Mapping):
        raise BoundedRepositoryCompressionError(
            "determinism must be an object"
        )
    _hash(normalized["determinism"])
    return normalized


def _named_mapping(
    value: Any,
    label: str,
    maximum: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise BoundedRepositoryCompressionError(
            f"{label} must be a non-empty object"
        )
    if len(value) > maximum:
        raise BoundedRepositoryCompressionError(
            f"{label} cannot exceed {maximum} entries"
        )
    normalized: dict[str, Any] = {}
    for item_id, item in value.items():
        key = _required_text(item_id, f"{label}_id")
        if key != key.strip():
            raise BoundedRepositoryCompressionError(
                f"{label}_id cannot contain outer whitespace"
            )
        normalized[key] = item
    return normalized


def _observe(
    block: Any,
    observers: Mapping[str, Observer],
    contexts: Mapping[str, Mapping[str, Any]],
    effect_runner: EffectRunner,
) -> list[dict[str, Any]]:
    vector: list[dict[str, Any]] = []
    for observer_id in sorted(observers):
        observer = observers[observer_id]
        if not callable(observer):
            raise BoundedRepositoryCompressionError(
                f"observer is not callable: {observer_id}"
            )
        for context_id in sorted(contexts):
            context = contexts[context_id]
            if not isinstance(context, Mapping):
                raise BoundedRepositoryCompressionError(
                    f"context must be an object: {context_id}"
                )
            observation = _execute_bounded(
                effect_runner,
                f"observe:{observer_id}:{context_id}",
                observer,
                deepcopy(dict(context)),
                deepcopy(block),
            )
            _canonical_size(observation)
            vector.append(
                {
                    "observer_id": observer_id,
                    "context_id": context_id,
                    "observation": deepcopy(observation),
                }
            )
    return vector


def _execute_bounded(
    effect_runner: EffectRunner,
    operation: str,
    function: Callable[..., Any],
    *arguments: Any,
) -> Any:
    result = effect_runner(operation, function, *arguments)
    try:
        normalized = _exact_fields(
            result,
            EFFECT_RESULT_FIELDS,
            "effect runner result",
        )
    except BoundedRepositoryCompressionError as exc:
        raise _EffectBoundaryUnknown(str(exc)) from exc
    if (
        normalized["status"] != "COMPLETED"
        or normalized["external_effects_blocked"] is not True
        or not isinstance(normalized["effects"], list)
        or normalized["effects"]
    ):
        raise _EffectBoundaryUnknown(
            "effect runner did not establish effect-free completion"
        )
    _canonical_size(normalized["value"])
    return deepcopy(normalized["value"])


def _first_mismatch(
    baseline: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    round_index: int,
) -> dict[str, Any] | None:
    for expected, actual in zip(baseline, candidate, strict=True):
        if expected != actual:
            return {
                "round": round_index,
                "observer_id": expected["observer_id"],
                "context_id": expected["context_id"],
                "baseline_observation": deepcopy(expected["observation"]),
                "candidate_observation": deepcopy(actual["observation"]),
            }
    return None


def _validate_vector(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise BoundedRepositoryCompressionError(f"{label} must be a list")
    normalized: list[dict[str, Any]] = []
    coordinates: set[tuple[str, str]] = set()
    for item in value:
        coordinate = _exact_fields(item, OBSERVATION_FIELDS, label)
        observer_id = _required_text(
            coordinate["observer_id"], "observer_id"
        )
        context_id = _required_text(coordinate["context_id"], "context_id")
        key = (observer_id, context_id)
        if key in coordinates:
            raise BoundedRepositoryCompressionError(
                f"{label} contains a duplicate coordinate"
            )
        coordinates.add(key)
        _hash(coordinate["observation"])
        normalized.append(coordinate)
    return normalized


def _block_id(block: Any, round_index: int, previous_id: str | None) -> str:
    return _hash(
        {
            "type": "bounded_compression_round_block",
            "version": 1,
            "ordinal": round_index,
            "parent_id": previous_id,
            "previous_append_id": previous_id,
            "content": block,
        }
    )


def _receipt(
    *,
    scope: Mapping[str, Any],
    round_bound: int,
    baseline_block_id: str,
    baseline_observation_vector: list[dict[str, Any]],
    rounds: list[dict[str, Any]],
    result: str,
    reason: str | None,
    mismatch_witness: dict[str, Any] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "scope": deepcopy(dict(scope)),
        "round_bound": round_bound,
        "baseline_block_id": baseline_block_id,
        "baseline_observation_vector": baseline_observation_vector,
        "rounds": rounds,
        "result": result,
        "reason": reason,
        "mismatch_witness": mismatch_witness,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "EQUIVALENT means no mismatch was observed only within the "
            "receipt-bound finite observer, context, platform, and round "
            "scope. It does not prove universal equivalence, authorize "
            "promotion, or grant truth, write, or execution authority."
        ),
    }
    return {**body, "receipt_id": _hash(body)}


def evaluate_repository_compression(
    *,
    baseline: Any,
    compress: Transform,
    reconstruct: Transform,
    observers: Mapping[str, Observer],
    contexts: Mapping[str, Mapping[str, Any]],
    rounds: int,
    scope: Mapping[str, Any],
    effect_runner: EffectRunner | None = None,
) -> dict[str, Any]:
    """Evaluate repeated reconstruction against one unchanged baseline."""
    if not isinstance(rounds, int) or isinstance(rounds, bool) or not (
        1 <= rounds <= MAX_ROUNDS
    ):
        raise BoundedRepositoryCompressionError(
            f"rounds must be an integer from 1 through {MAX_ROUNDS}"
        )
    if not callable(compress) or not callable(reconstruct):
        raise BoundedRepositoryCompressionError(
            "compress and reconstruct must be callable"
        )
    normalized_scope = _validate_scope(scope)
    normalized_observers = _named_mapping(
        observers, "observers", MAX_OBSERVERS
    )
    normalized_contexts = _named_mapping(contexts, "contexts", MAX_CONTEXTS)
    _canonical_size(baseline)

    baseline_copy = deepcopy(baseline)
    baseline_id = _block_id(baseline_copy, 0, None)
    if effect_runner is None:
        return _receipt(
            scope=normalized_scope,
            round_bound=rounds,
            baseline_block_id=baseline_id,
            baseline_observation_vector=[],
            rounds=[],
            result=UNKNOWN,
            reason=EFFECT_RUNNER_REQUIRED,
            mismatch_witness=None,
        )
    if not callable(effect_runner):
        raise BoundedRepositoryCompressionError(
            "effect_runner must be callable"
        )
    try:
        baseline_vector = _observe(
            baseline_copy,
            normalized_observers,
            normalized_contexts,
            effect_runner,
        )
        current = deepcopy(baseline_copy)
        previous_id = baseline_id
        round_records: list[dict[str, Any]] = []

        for round_index in range(1, rounds + 1):
            source_size = _canonical_size(current)
            representation = _execute_bounded(
                effect_runner,
                f"compress:{round_index}",
                compress,
                deepcopy(current),
            )
            representation_size = _canonical_size(representation)
            representation_id = _hash(
                {
                    "type": "bounded_compression_representation",
                    "version": 1,
                    "round": round_index,
                    "content": representation,
                }
            )
            size_reducing = representation_size < source_size
            if not size_reducing:
                return _receipt(
                    scope=normalized_scope,
                    round_bound=rounds,
                    baseline_block_id=baseline_id,
                    baseline_observation_vector=baseline_vector,
                    rounds=round_records,
                    result=UNKNOWN,
                    reason=NOT_SIZE_REDUCING,
                    mismatch_witness=None,
                )

            reconstructed = _execute_bounded(
                effect_runner,
                f"reconstruct:{round_index}",
                reconstruct,
                deepcopy(representation),
            )
            _canonical_size(reconstructed)
            reconstructed_id = _block_id(
                reconstructed, round_index, previous_id
            )
            vector = _observe(
                reconstructed,
                normalized_observers,
                normalized_contexts,
                effect_runner,
            )
            record = {
                "round": round_index,
                "source_block_id": previous_id,
                "compressed_representation_id": representation_id,
                "reconstructed_block_id": reconstructed_id,
                "source_size_bytes": source_size,
                "representation_size_bytes": representation_size,
                "size_reducing": True,
                "observation_vector": vector,
            }
            round_records.append(record)
            witness = _first_mismatch(
                baseline_vector, vector, round_index
            )
            if witness is not None:
                return _receipt(
                    scope=normalized_scope,
                    round_bound=rounds,
                    baseline_block_id=baseline_id,
                    baseline_observation_vector=baseline_vector,
                    rounds=round_records,
                    result=DISTINCTION_LOST,
                    reason=None,
                    mismatch_witness=witness,
                )
            current = reconstructed
            previous_id = reconstructed_id
    except _EffectBoundaryUnknown:
        return _receipt(
            scope=normalized_scope,
            round_bound=rounds,
            baseline_block_id=baseline_id,
            baseline_observation_vector=[],
            rounds=[],
            result=UNKNOWN,
            reason=EFFECT_BOUNDARY_UNVERIFIED,
            mismatch_witness=None,
        )
    except (BoundedRepositoryCompressionError, CanonicalValueError):
        raise
    except Exception as exc:
        return _receipt(
            scope=normalized_scope,
            round_bound=rounds,
            baseline_block_id=_block_id(baseline_copy, 0, None),
            baseline_observation_vector=[],
            rounds=[],
            result=UNKNOWN,
            reason=f"{EVALUATION_ERROR}:{type(exc).__name__}",
            mismatch_witness=None,
        )

    return _receipt(
        scope=normalized_scope,
        round_bound=rounds,
        baseline_block_id=baseline_id,
        baseline_observation_vector=baseline_vector,
        rounds=round_records,
        result=EQUIVALENT,
        reason=None,
        mismatch_witness=None,
    )


def verify_compression_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Verify exact schema, bounded semantics, authority, and identity."""
    violations: list[str] = []
    actual_id = receipt.get("receipt_id") if isinstance(receipt, Mapping) else None
    expected_id: str | None = None
    try:
        normalized = _exact_fields(
            receipt,
            RECEIPT_BODY_FIELDS | {"receipt_id"},
            "receipt",
        )
        if normalized["type"] != RECEIPT_TYPE:
            raise BoundedRepositoryCompressionError("receipt type is invalid")
        if normalized["version"] != RECEIPT_VERSION:
            raise BoundedRepositoryCompressionError(
                "receipt version is invalid"
            )
        _validate_scope(normalized["scope"])
        if not isinstance(normalized["round_bound"], int) or isinstance(
            normalized["round_bound"], bool
        ) or not (1 <= normalized["round_bound"] <= MAX_ROUNDS):
            raise BoundedRepositoryCompressionError(
                "receipt round_bound is invalid"
            )
        _sha256(normalized["baseline_block_id"], "baseline_block_id")
        baseline_vector = _validate_vector(
            normalized["baseline_observation_vector"],
            "baseline observation vector",
        )
        if not isinstance(normalized["rounds"], list):
            raise BoundedRepositoryCompressionError("rounds must be a list")
        previous_id = normalized["baseline_block_id"]
        round_vectors: dict[int, list[dict[str, Any]]] = {}
        for expected_round, item in enumerate(normalized["rounds"], start=1):
            record = _exact_fields(item, ROUND_FIELDS, "round record")
            if record["round"] != expected_round:
                raise BoundedRepositoryCompressionError(
                    "round records must be consecutive"
                )
            for field in (
                "source_block_id",
                "compressed_representation_id",
                "reconstructed_block_id",
            ):
                _sha256(record[field], field)
            if record["source_block_id"] != previous_id:
                raise BoundedRepositoryCompressionError(
                    "round source does not preserve prior reconstructed identity"
                )
            if record["size_reducing"] is not True or not (
                record["representation_size_bytes"]
                < record["source_size_bytes"]
            ):
                raise BoundedRepositoryCompressionError(
                    "round record is not size reducing"
                )
            round_vector = _validate_vector(
                record["observation_vector"],
                "round observation vector",
            )
            round_vectors[expected_round] = round_vector
            previous_id = record["reconstructed_block_id"]
        if normalized["result"] not in {
            EQUIVALENT,
            DISTINCTION_LOST,
            UNKNOWN,
        }:
            raise BoundedRepositoryCompressionError("receipt result is invalid")
        if normalized["result"] == EQUIVALENT:
            if len(normalized["rounds"]) != normalized["round_bound"]:
                raise BoundedRepositoryCompressionError(
                    "equivalent receipt did not evaluate every round"
                )
            if normalized["reason"] is not None or normalized[
                "mismatch_witness"
            ] is not None:
                raise BoundedRepositoryCompressionError(
                    "equivalent receipt cannot carry failure evidence"
                )
            if any(
                vector != baseline_vector
                for vector in round_vectors.values()
            ):
                raise BoundedRepositoryCompressionError(
                    "equivalent receipt contains an observation mismatch"
                )
        elif normalized["result"] == DISTINCTION_LOST:
            witness = _exact_fields(
                normalized["mismatch_witness"],
                WITNESS_FIELDS,
                "mismatch witness",
            )
            if witness["baseline_observation"] == witness[
                "candidate_observation"
            ]:
                raise BoundedRepositoryCompressionError(
                    "mismatch witness observations must differ"
                )
            if normalized["reason"] is not None:
                raise BoundedRepositoryCompressionError(
                    "distinction-lost receipt cannot carry unknown reason"
                )
            witness_round = witness["round"]
            if witness_round not in round_vectors:
                raise BoundedRepositoryCompressionError(
                    "mismatch witness round is unavailable"
                )
            baseline_coordinates = {
                (item["observer_id"], item["context_id"]): item[
                    "observation"
                ]
                for item in baseline_vector
            }
            candidate_coordinates = {
                (item["observer_id"], item["context_id"]): item[
                    "observation"
                ]
                for item in round_vectors[witness_round]
            }
            witness_key = (witness["observer_id"], witness["context_id"])
            if (
                baseline_coordinates.get(witness_key)
                != witness["baseline_observation"]
                or candidate_coordinates.get(witness_key)
                != witness["candidate_observation"]
            ):
                raise BoundedRepositoryCompressionError(
                    "mismatch witness does not match recorded observations"
                )
        elif normalized["reason"] is None:
            raise BoundedRepositoryCompressionError(
                "unknown receipt requires a reason"
            )
        if normalized["accepted"] is not False or normalized[
            "truth_claimed"
        ] is not False:
            raise BoundedRepositoryCompressionError(
                "receipt must remain observational"
            )
        if normalized["write_authority"] != "NONE" or normalized[
            "execution_authority"
        ] != "NONE":
            raise BoundedRepositoryCompressionError(
                "receipt must carry no write or execution authority"
            )
        body = {
            key: deepcopy(value)
            for key, value in normalized.items()
            if key != "receipt_id"
        }
        expected_id = _hash(body)
        _sha256(actual_id, "receipt_id")
        if actual_id != expected_id:
            raise BoundedRepositoryCompressionError(
                "compression receipt identity mismatch"
            )
    except (BoundedRepositoryCompressionError, CanonicalValueError) as exc:
        violations.append(str(exc))

    return {
        "valid": not violations,
        "receipt_id": actual_id,
        "expected_receipt_id": expected_id,
        "violations": violations,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
