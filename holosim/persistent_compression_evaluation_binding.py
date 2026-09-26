"""Gate compression evaluation through the current persisted baseline."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from holosim.canonical import stable_hash
from holosim.compression_observer_evaluation_binding import (
    evaluate_bound_repository_compression,
)
from holosim.persistent_baseline_content_binding import (
    CURRENT_BASELINE_BOUND,
    bind_persistent_baseline_content,
)
from holosim.persistent_baseline_transition import (
    PersistentBaselineTransitionStore,
)


class PersistentCompressionEvaluationBindingError(ValueError):
    """Raised when compression is not bound to the current persisted content."""


def evaluate_current_persistent_repository_compression(
    *,
    store: PersistentBaselineTransitionStore,
    content_identity_receipt: Mapping[str, Any],
    identity_function: Callable[[Any], Any],
    binding_receipt: Mapping[str, Any],
    coverage_receipt: Mapping[str, Any],
    baseline: Any,
    compress: Callable[[Any], Any],
    reconstruct: Callable[[Any], Any],
    observers: Mapping[str, Callable[..., Any]],
    contexts: Mapping[str, Mapping[str, Any]],
    rounds: int,
    scope: Mapping[str, Any],
    effect_runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Evaluate compression only for exact current persisted baseline content.

    The content identity receipt is first replayed against the supplied identity
    function and bound to the live reconstructed persistence head.

    The exact baseline supplied to compression must then be canonically
    identical to the baseline stored in that verified content identity receipt.

    Only after those checks succeed is control delegated to the existing
    observer-bound compression evaluator.

    This wrapper grants no truth, persistence, write, execution, compression,
    promotion, or other authority.
    """

    persistent_binding = bind_persistent_baseline_content(
        store=store,
        content_identity_receipt=content_identity_receipt,
        identity_function=identity_function,
    )

    if persistent_binding.get("status") != CURRENT_BASELINE_BOUND:
        raise PersistentCompressionEvaluationBindingError(
            "baseline content must be bound to the current persisted head"
        )

    if persistent_binding.get("binding_complete") is not True:
        raise PersistentCompressionEvaluationBindingError(
            "baseline content must be bound to the current persisted head"
        )

    try:
        supplied_baseline_hash = stable_hash(baseline)
        bound_baseline_hash = stable_hash(
            content_identity_receipt["baseline"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PersistentCompressionEvaluationBindingError(
            "compression baseline must be canonical bound content"
        ) from exc

    if supplied_baseline_hash != bound_baseline_hash:
        raise PersistentCompressionEvaluationBindingError(
            "compression baseline must exactly match bound baseline content"
        )

    return evaluate_bound_repository_compression(
        binding_receipt=binding_receipt,
        coverage_receipt=coverage_receipt,
        baseline=baseline,
        compress=compress,
        reconstruct=reconstruct,
        observers=observers,
        contexts=contexts,
        rounds=rounds,
        scope=scope,
        effect_runner=effect_runner,
    )