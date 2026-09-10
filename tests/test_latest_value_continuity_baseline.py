import json
from pathlib import Path

from holosim.continuity_baseline_benchmark import (
    compare_continuity_conditions,
)
from holosim.public_continuity_benchmark import (
    PUBLIC_CONDITION_TYPE,
    PUBLIC_CONDITION_VERSION,
    load_public_continuity_fixture,
    score_public_continuity_condition,
)


ROOT = Path(__file__).resolve().parents[1]

FIXTURE_PATH = (
    ROOT
    / "benchmarks"
    / "continuity-v1.fixture.json"
)

HOLO_REFERENCE_PATH = (
    ROOT
    / "benchmarks"
    / "results"
    / "holo-reference.result.json"
)


def test_latest_value_only_baseline_against_same_frozen_fixture():
    """
    Characterize a deliberately minimal latest-value store.

    This baseline preserves only the currently stored value.

    It has no independent representation for:
    - residual uncertainty,
    - correction lineage, or
    - stale-continuation blocking.

    The test does not claim that every key/value store behaves this way.
    It measures this exact baseline against the exact same frozen fixture
    used by the committed HOLO reference result.
    """

    fixture = load_public_continuity_fixture(
        FIXTURE_PATH
    )

    latest_value_condition = {
        "type": PUBLIC_CONDITION_TYPE,
        "version": PUBLIC_CONDITION_VERSION,
        "fixture_hash": fixture["fixture_hash"],
        "condition_id": "naive-latest-value-only",
        "recovered_claim_ids": list(
            fixture["latest_justified_claim_ids"]
        ),
        "claimed_current_claim_ids": list(
            fixture["latest_justified_claim_ids"]
        ),
        "preserved_uncertainty_claim_ids": [],
        "reconstructed_lineage_edges": [],
        "stale_continuation_decision": "UNKNOWN",
    }

    baseline = score_public_continuity_condition(
        fixture=fixture,
        condition=latest_value_condition,
    )

    holo_reference = json.loads(
        HOLO_REFERENCE_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert (
        holo_reference["fixture_hash"]
        == fixture["fixture_hash"]
    )

    comparison = compare_continuity_conditions(
        baseline=baseline,
        candidate=holo_reference,
    )

    # Latest-value storage can preserve the newest value.
    assert (
        baseline["metrics"]["latest_justified_recall"]
        == 1.0
    )

    # It does not resurrect the overwritten value as current.
    assert (
        baseline["metrics"][
            "superseded_resurrection_count"
        ]
        == 0
    )

    # But this exact baseline has no representation for these
    # continuity properties.
    assert (
        baseline["metrics"]["uncertainty_recall"]
        == 0.0
    )
    assert (
        baseline["metrics"]["lineage_recall"]
        == 0.0
    )
    assert (
        baseline["metrics"][
            "stale_continuation_blocked"
        ]
        is False
    )

    assert (
        baseline["metrics"][
            "passes_bounded_continuity_fixture"
        ]
        is False
    )

    # The committed HOLO reference passes the same frozen fixture.
    assert (
        holo_reference["metrics"][
            "passes_bounded_continuity_fixture"
        ]
        is True
    )

    # The difference is specifically uncertainty + lineage +
    # stale-continuation behavior, not latest-value recall.
    assert (
        comparison["delta"][
            "latest_justified_recall"
        ]
        == 0.0
    )
    assert (
        comparison["delta"][
            "superseded_resurrection_count"
        ]
        == 0
    )
    assert (
        comparison["delta"]["uncertainty_recall"]
        == 1.0
    )
    assert (
        comparison["delta"]["lineage_recall"]
        == 1.0
    )

    assert (
        comparison[
            "candidate_passes_where_baseline_does_not"
        ]
        is True
    )

    # Comparison does not create truth or authority.
    assert comparison["truth_claimed"] is False
    assert comparison["accepted"] is False
    assert comparison["write_authority"] == "NONE"