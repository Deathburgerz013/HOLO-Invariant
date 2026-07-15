"""Executable checks for the finite terrain aggregation fixture.

This module verifies one bounded arithmetic example. It does not establish
an empirical claim or a universal aggregation invariant.
"""

from fractions import Fraction


COUNTS = {
    "candidate": {
        "easy": {"success": 81, "total": 87},
        "hard": {"success": 192, "total": 263},
    },
    "baseline": {
        "easy": {"success": 234, "total": 270},
        "hard": {"success": 55, "total": 80},
    },
}


def rate(record):
    return Fraction(record["success"], record["total"])


def layer_rates(arm):
    return {
        layer: rate(record)
        for layer, record in COUNTS[arm].items()
    }


def pooled_counts(arm):
    records = COUNTS[arm].values()
    return {
        "success": sum(record["success"] for record in records),
        "total": sum(record["total"] for record in records),
    }


def pooled_rate(arm):
    return rate(pooled_counts(arm))


def unweighted_layer_mean(arm):
    rates = list(layer_rates(arm).values())
    return sum(rates, Fraction()) / len(rates)


def two_step_aggregate(arm):
    layers = {
        name: dict(record) for name, record in COUNTS[arm].items()
    }
    return {
        "endpoint": pooled_counts(arm),
        "loss_ledger": {
            "path": ["fine", "layer", "pooled"],
            "retained_strata": layers,
            "discarded_at_endpoint": ["layer_identity"],
            "reconstructable_from_endpoint": False,
        },
    }


def direct_aggregate(arm):
    return {
        "endpoint": pooled_counts(arm),
        "loss_ledger": {
            "path": ["fine", "pooled"],
            "retained_strata": None,
            "discarded_at_endpoint": [
                "layer_identity",
                "layer_counts",
                "conditional_direction",
            ],
            "reconstructable_from_endpoint": False,
        },
    }


def hazard_report():
    severities = [0] * 999 + [1000]
    count = len(severities)
    total = sum(severities)
    mean = Fraction(total, count)
    maximum = max(severities)
    hazard_count = sum(value > 100 for value in severities)
    return {
        "count": count,
        "mean": mean,
        "maximum": maximum,
        "hazard_count": hazard_count,
        "hazard_rate": Fraction(hazard_count, count),
        "mean_check_passed": mean <= 1,
        "maximum_severity_invariant_passed": maximum <= 100,
        "accepted": False,
        "write_authority": "NONE",
    }


def fixture_report():
    return {
        "fixture_id": "finite:aggregation-reversal:v1",
        "candidate_layer_rates": layer_rates("candidate"),
        "baseline_layer_rates": layer_rates("baseline"),
        "candidate_pooled_rate": pooled_rate("candidate"),
        "baseline_pooled_rate": pooled_rate("baseline"),
        "candidate_unweighted_layer_mean": unweighted_layer_mean(
            "candidate"
        ),
        "baseline_unweighted_layer_mean": unweighted_layer_mean(
            "baseline"
        ),
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This report verifies one finite arithmetic fixture only."
        ),
    }


def test_candidate_is_better_inside_each_declared_layer():
    candidate = layer_rates("candidate")
    baseline = layer_rates("baseline")

    assert candidate["easy"] == Fraction(27, 29)
    assert baseline["easy"] == Fraction(13, 15)
    assert candidate["easy"] - baseline["easy"] == Fraction(28, 435)
    assert candidate["easy"] > baseline["easy"]

    assert candidate["hard"] == Fraction(192, 263)
    assert baseline["hard"] == Fraction(11, 16)
    assert candidate["hard"] - baseline["hard"] == Fraction(179, 4208)
    assert candidate["hard"] > baseline["hard"]


def test_pooled_aggregation_reverses_the_comparison_direction():
    assert pooled_counts("candidate") == {"success": 273, "total": 350}
    assert pooled_counts("baseline") == {"success": 289, "total": 350}
    assert pooled_rate("candidate") == Fraction(39, 50)
    assert pooled_rate("baseline") == Fraction(289, 350)
    assert pooled_rate("candidate") - pooled_rate("baseline") == Fraction(
        -8, 175
    )
    assert pooled_rate("candidate") < pooled_rate("baseline")


def test_unweighted_layer_mean_and_pooled_mean_answer_differently():
    candidate = unweighted_layer_mean("candidate")
    baseline = unweighted_layer_mean("baseline")

    assert candidate == Fraction(12669, 15254)
    assert baseline == Fraction(373, 480)
    assert candidate > baseline
    assert pooled_rate("candidate") < pooled_rate("baseline")


def test_changed_layer_weights_explain_the_reversal_pressure():
    candidate_hard_weight = Fraction(
        COUNTS["candidate"]["hard"]["total"],
        pooled_counts("candidate")["total"],
    )
    baseline_hard_weight = Fraction(
        COUNTS["baseline"]["hard"]["total"],
        pooled_counts("baseline")["total"],
    )

    assert candidate_hard_weight == Fraction(263, 350)
    assert baseline_hard_weight == Fraction(8, 35)
    assert candidate_hard_weight > baseline_hard_weight


def test_direct_and_two_step_paths_have_equal_pooled_endpoints():
    for arm in COUNTS:
        assert two_step_aggregate(arm)["endpoint"] == direct_aggregate(arm)[
            "endpoint"
        ]


def test_equal_endpoints_do_not_make_loss_ledgers_equal():
    for arm in COUNTS:
        two_step = two_step_aggregate(arm)
        direct = direct_aggregate(arm)

        assert two_step["loss_ledger"] != direct["loss_ledger"]
        assert two_step["loss_ledger"]["retained_strata"] is not None
        assert direct["loss_ledger"]["retained_strata"] is None
        assert "conditional_direction" in direct["loss_ledger"][
            "discarded_at_endpoint"
        ]


def test_pooled_candidate_endpoint_has_multiple_layer_reconstructions():
    original = {
        "easy": {"success": 81, "total": 87},
        "hard": {"success": 192, "total": 263},
    }
    alternative = {
        "easy": {"success": 80, "total": 100},
        "hard": {"success": 193, "total": 250},
    }

    def totals(layers):
        return {
            "success": sum(item["success"] for item in layers.values()),
            "total": sum(item["total"] for item in layers.values()),
        }

    assert original != alternative
    assert totals(original) == {"success": 273, "total": 350}
    assert totals(alternative) == {"success": 273, "total": 350}


def test_rare_hazard_passes_mean_check_but_fails_local_invariant():
    report = hazard_report()

    assert report["count"] == 1000
    assert report["mean"] == 1
    assert report["maximum"] == 1000
    assert report["hazard_count"] == 1
    assert report["hazard_rate"] == Fraction(1, 1000)
    assert report["mean_check_passed"] is True
    assert report["maximum_severity_invariant_passed"] is False


def test_hazard_summary_retains_more_than_the_mean():
    report = hazard_report()

    required = {
        "count",
        "mean",
        "maximum",
        "hazard_count",
        "hazard_rate",
        "maximum_severity_invariant_passed",
    }
    assert required <= set(report)


def test_fixture_reports_cannot_accept_or_write():
    aggregate = fixture_report()
    hazard = hazard_report()

    assert aggregate["accepted"] is False
    assert aggregate["write_authority"] == "NONE"
    assert hazard["accepted"] is False
    assert hazard["write_authority"] == "NONE"