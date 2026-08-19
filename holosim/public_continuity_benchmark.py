"""Public, system-neutral continuity benchmark boundary."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from holosim.continuity_baseline_benchmark import (
    ContinuityBaselineBenchmarkError,
    score_continuity_condition,
)


PUBLIC_CONDITION_TYPE = "holo_continuity_condition"
PUBLIC_CONDITION_VERSION = 1

CONDITION_FIELDS = {
    "type",
    "version",
    "fixture_hash",
    "condition_id",
    "recovered_claim_ids",
    "claimed_current_claim_ids",
    "preserved_uncertainty_claim_ids",
    "reconstructed_lineage_edges",
    "stale_continuation_decision",
}


class PublicContinuityBenchmarkError(ValueError):
    """Raised when a public benchmark input cannot be scored."""


def _load_json_object(
    path: str | Path,
    *,
    label: str,
) -> dict[str, Any]:
    source = Path(path)

    try:
        value = json.loads(
            source.read_text(encoding="utf-8")
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise PublicContinuityBenchmarkError(
            f"{label} could not be loaded: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise PublicContinuityBenchmarkError(
            f"{label} must contain a JSON object"
        )

    return value


def load_public_continuity_fixture(
    path: str | Path,
) -> dict[str, Any]:
    """Load and verify a committed public fixture."""
    fixture = _load_json_object(
        path,
        label="fixture",
    )

    probe = {
        "type": PUBLIC_CONDITION_TYPE,
        "version": PUBLIC_CONDITION_VERSION,
        "fixture_hash": fixture.get("fixture_hash"),
        "condition_id": "fixture-integrity-probe",
        "recovered_claim_ids": [],
        "claimed_current_claim_ids": [],
        "preserved_uncertainty_claim_ids": [],
        "reconstructed_lineage_edges": [],
        "stale_continuation_decision": "UNKNOWN",
    }

    try:
        score_public_continuity_condition(
            fixture=fixture,
            condition=probe,
        )
    except PublicContinuityBenchmarkError:
        raise
    except Exception as exc:
        raise PublicContinuityBenchmarkError(
            str(exc)
        ) from exc

    return fixture


def _validate_condition(
    condition: Mapping[str, Any],
    *,
    fixture_hash: str,
) -> dict[str, Any]:
    if not isinstance(condition, Mapping):
        raise PublicContinuityBenchmarkError(
            "condition must be a mapping"
        )

    if set(condition) != CONDITION_FIELDS:
        raise PublicContinuityBenchmarkError(
            "condition fields are invalid"
        )

    if condition.get("type") != PUBLIC_CONDITION_TYPE:
        raise PublicContinuityBenchmarkError(
            "condition type is invalid"
        )

    if (
        condition.get("version")
        != PUBLIC_CONDITION_VERSION
    ):
        raise PublicContinuityBenchmarkError(
            "condition version is invalid"
        )

    if condition.get("fixture_hash") != fixture_hash:
        raise PublicContinuityBenchmarkError(
            "condition fixture_hash does not match"
        )

    try:
        return json.loads(
            json.dumps(
                dict(condition),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as exc:
        raise PublicContinuityBenchmarkError(
            "condition must contain only JSON values"
        ) from exc


def score_public_continuity_condition(
    *,
    fixture: Mapping[str, Any],
    condition: Mapping[str, Any],
) -> dict[str, Any]:
    """Score one closed public condition against one exact fixture."""
    if not isinstance(fixture, Mapping):
        raise PublicContinuityBenchmarkError(
            "fixture must be a mapping"
        )

    fixture_hash = fixture.get("fixture_hash")
    if not isinstance(fixture_hash, str) or not fixture_hash:
        raise PublicContinuityBenchmarkError(
            "fixture requires fixture_hash"
        )

    validated = _validate_condition(
        condition,
        fixture_hash=fixture_hash,
    )

    try:
        return score_continuity_condition(
            fixture=fixture,
            condition_id=validated["condition_id"],
            recovered_claim_ids=validated[
                "recovered_claim_ids"
            ],
            claimed_current_claim_ids=validated[
                "claimed_current_claim_ids"
            ],
            preserved_uncertainty_claim_ids=validated[
                "preserved_uncertainty_claim_ids"
            ],
            reconstructed_lineage_edges=validated[
                "reconstructed_lineage_edges"
            ],
            stale_continuation_decision=validated[
                "stale_continuation_decision"
            ],
        )
    except ContinuityBaselineBenchmarkError as exc:
        raise PublicContinuityBenchmarkError(
            str(exc)
        ) from exc


def run_public_continuity_benchmark(
    args: argparse.Namespace,
) -> int:
    """Load, score, and print one public continuity condition."""
    try:
        if args.benchmark_kind != "continuity":
            raise PublicContinuityBenchmarkError(
                "unsupported benchmark kind"
            )

        fixture = load_public_continuity_fixture(
            args.fixture
        )
        condition = _load_json_object(
            args.condition,
            label="condition",
        )
        result = score_public_continuity_condition(
            fixture=fixture,
            condition=condition,
        )
    except PublicContinuityBenchmarkError as exc:
        print(
            f"Continuity benchmark blocked: {exc}",
            file=sys.stderr,
        )
        return 2

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0