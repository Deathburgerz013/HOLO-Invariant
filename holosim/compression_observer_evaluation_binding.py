"""Gate repository compression evaluation through verified observer binding."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from holosim.bounded_repository_compression_evaluator import (
    evaluate_repository_compression,
)
from holosim.compression_observer_runtime_binding import (
    verify_compression_observer_runtime_binding_receipt,
)


class CompressionObserverEvaluationBindingError(ValueError):
    """Raised when compression evaluation is not observer-bound."""


def evaluate_bound_repository_compression(
    *,
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
    """Evaluate compression only through the verified bound observer mapping.

    The supplied binding receipt must replay successfully against the supplied
    coverage receipt and the exact runtime observer mapping that will be passed
    to the repository compression evaluator.

    Observer binding verification occurs before compression, reconstruction,
    effect execution, or observer execution.

    This wrapper grants no additional truth, write, execution, compression, or
    promotion authority. The bounded repository compression evaluator retains
    its existing result semantics and authority boundary.
    """

    binding_check = (
        verify_compression_observer_runtime_binding_receipt(
            receipt=binding_receipt,
            coverage_receipt=coverage_receipt,
            observers=observers,
        )
    )

    if not binding_check["valid"]:
        raise CompressionObserverEvaluationBindingError(
            "observer binding must verify before compression evaluation"
        )

    if binding_receipt.get("status") != "BOUND":
        raise CompressionObserverEvaluationBindingError(
            "observer binding must be complete before compression evaluation"
        )

    if binding_receipt.get("binding_complete") is not True:
        raise CompressionObserverEvaluationBindingError(
            "observer binding must be complete before compression evaluation"
        )

    return evaluate_repository_compression(
        baseline=baseline,
        compress=compress,
        reconstruct=reconstruct,
        observers=observers,
        contexts=contexts,
        rounds=rounds,
        scope=scope,
        effect_runner=effect_runner,
    )