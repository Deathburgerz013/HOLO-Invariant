from __future__ import annotations


def test_derives_distinction_matrix_from_executed_checks() -> None:
    from holosim.experimental_distinguishability import derive_distinguishability

    candidates = {
        "A": {"value": 0},
        "B": {"value": 1},
        "C": {"value": 2},
    }

    checks = {
        "check_x": lambda candidate: candidate["value"] > 0,
        "check_y": lambda candidate: candidate["value"] < 2,
        "check_z": lambda candidate: True,
    }

    receipt = derive_distinguishability(
        candidates=candidates,
        checks=checks,
    )

    assert receipt["outcome_matrix"] == {
        "A": {"check_x": False, "check_y": True, "check_z": True},
        "B": {"check_x": True, "check_y": True, "check_z": True},
        "C": {"check_x": True, "check_y": False, "check_z": True},
    }

    assert receipt["partitions"] == {
        "check_x": [["A"], ["B", "C"]],
        "check_y": [["A", "B"], ["C"]],
        "check_z": [["A", "B", "C"]],
    }

    assert receipt["ranking"] == ["check_x", "check_y", "check_z"]
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"


def test_uniform_check_ranks_last_with_zero_discrimination() -> None:
    from holosim.experimental_distinguishability import derive_distinguishability

    candidates = {
        "A": {"value": 0},
        "B": {"value": 1},
        "C": {"value": 2},
    }

    checks = {
        "splitter": lambda candidate: candidate["value"] > 0,
        "uniform": lambda candidate: True,
    }

    receipt = derive_distinguishability(candidates=candidates, checks=checks)

    assert receipt["ranking"] == ["splitter", "uniform"]
    assert receipt["partitions"]["uniform"] == [["A", "B", "C"]]


def test_failed_check_cell_is_unavailable_not_invented() -> None:
    from holosim.experimental_distinguishability import (
        ObservationUnavailable,
        derive_distinguishability,
    )

    candidates = {
        "A": {"value": 0},
        "B": {},
    }

    checks = {
        "requires_value": lambda candidate: (
            candidate["value"] > 0
            if "value" in candidate
            else (_ for _ in ()).throw(ObservationUnavailable())
        ),
    }

    receipt = derive_distinguishability(candidates=candidates, checks=checks)

    assert receipt["outcome_matrix"]["A"]["requires_value"] is False
    assert receipt["outcome_matrix"]["B"]["requires_value"] == "UNAVAILABLE"
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"


def test_same_observations_produce_same_receipt_hash() -> None:
    from holosim.experimental_distinguishability import derive_distinguishability

    candidates = {"A": {"value": 0}, "B": {"value": 1}}
    checks = {"splitter": lambda candidate: candidate["value"] > 0}

    first = derive_distinguishability(candidates=candidates, checks=checks)
    second = derive_distinguishability(candidates=candidates, checks=checks)

    assert first["receipt_hash"] == second["receipt_hash"]
    assert len(first["receipt_hash"]) == 64


def test_ranking_prefers_more_observed_pair_separation() -> None:
    from holosim.experimental_distinguishability import (
        ObservationUnavailable,
        derive_distinguishability,
    )

    candidates = {
        "A": {"value": 0},
        "B": {"value": 1},
        "C": {"value": 2},
        "D": {},
    }

    checks = {
        "full_split": lambda candidate: (
            candidate["value"] % 2
            if "value" in candidate
            else (_ for _ in ()).throw(ObservationUnavailable())
        ),
        "partial_split": lambda candidate: (
            candidate["value"] > 0
            if "value" in candidate
            else (_ for _ in ()).throw(ObservationUnavailable())
        ),
    }

    receipt = derive_distinguishability(candidates=candidates, checks=checks)
    assert receipt["ranking"][0] == "full_split"


def test_ranking_prefers_check_that_separates_more_candidate_pairs() -> None:
    from holosim.experimental_distinguishability import derive_distinguishability

    candidates = {
        "A": {"value": 0},
        "B": {"value": 1},
        "C": {"value": 2},
        "D": {"value": 3},
    }

    checks = {
        "a_imbalanced": lambda candidate: candidate["value"] == 0,
        "z_balanced": lambda candidate: candidate["value"] < 2,
    }

    receipt = derive_distinguishability(candidates=candidates, checks=checks)
    assert receipt["ranking"] == ["z_balanced", "a_imbalanced"]


def test_ranking_never_grants_acceptance_or_write_authority() -> None:
    from holosim.experimental_distinguishability import derive_distinguishability

    candidates = {"A": {"value": 0}, "B": {"value": 1}}
    checks = {"perfect_split": lambda candidate: candidate["value"]}

    receipt = derive_distinguishability(candidates=candidates, checks=checks)

    assert receipt["discrimination_scores"]["perfect_split"] == 1
    assert receipt["ranking"] == ["perfect_split"]
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"


def test_undeclared_candidate_does_not_affect_receipt() -> None:
    from holosim.experimental_distinguishability import derive_distinguishability

    candidates = {"A": {"value": 0}, "B": {"value": 1}}
    checks = {"splitter": lambda candidate: candidate["value"] > 0}

    receipt = derive_distinguishability(candidates=candidates, checks=checks)

    assert set(receipt["outcome_matrix"]) == {"A", "B"}
    assert "C" not in receipt["outcome_matrix"]
    assert receipt["partitions"]["splitter"] == [["A"], ["B"]]


def test_new_candidate_affects_result_only_after_declaration() -> None:
    from holosim.experimental_distinguishability import derive_distinguishability

    checks = {"parity": lambda candidate: candidate["value"] % 2}

    before = derive_distinguishability(
        candidates={"A": {"value": 0}, "B": {"value": 1}},
        checks=checks,
    )
    after = derive_distinguishability(
        candidates={"A": {"value": 0}, "B": {"value": 1}, "C": {"value": 2}},
        checks=checks,
    )

    assert before["partitions"]["parity"] == [["A"], ["B"]]
    assert after["partitions"]["parity"] == [["A", "C"], ["B"]]
    assert before["discrimination_scores"]["parity"] == 1
    assert after["discrimination_scores"]["parity"] == 2
    assert before["receipt_hash"] != after["receipt_hash"]


def test_unavailable_cells_do_not_increase_discrimination_score() -> None:
    from holosim.experimental_distinguishability import (
        ObservationUnavailable,
        derive_distinguishability,
    )

    candidates = {
        "A": {"value": 0},
        "B": {"value": 1},
        "C": {},
        "D": {},
    }

    checks = {
        "partial": lambda candidate: (
            candidate["value"] > 0
            if "value" in candidate
            else (_ for _ in ()).throw(ObservationUnavailable())
        ),
    }

    receipt = derive_distinguishability(candidates=candidates, checks=checks)

    assert receipt["outcome_matrix"]["C"]["partial"] == "UNAVAILABLE"
    assert receipt["outcome_matrix"]["D"]["partial"] == "UNAVAILABLE"
    assert receipt["partitions"]["partial"] == [["A"], ["B"]]
    assert receipt["discrimination_scores"]["partial"] == 1


def test_literal_unavailable_string_is_still_an_observed_outcome() -> None:
    from holosim.experimental_distinguishability import derive_distinguishability

    candidates = {
        "A": {"value": "UNAVAILABLE"},
        "B": {"value": "READY"},
    }
    checks = {"status": lambda candidate: candidate["value"]}

    receipt = derive_distinguishability(candidates=candidates, checks=checks)

    assert receipt["outcome_matrix"]["A"]["status"] == "UNAVAILABLE"
    assert receipt["outcome_matrix"]["B"]["status"] == "READY"
    assert receipt["partitions"]["status"] == [["A"], ["B"]]
    assert receipt["discrimination_scores"]["status"] == 1


def test_programming_error_is_not_silently_marked_unavailable() -> None:
    from holosim.experimental_distinguishability import derive_distinguishability

    candidates = {"A": {"value": 1}}

    def broken_check(candidate):
        raise RuntimeError("bug inside check")

    checks = {"broken": broken_check}

    try:
        derive_distinguishability(candidates=candidates, checks=checks)
    except RuntimeError as exc:
        assert str(exc) == "bug inside check"
    else:
        raise AssertionError(
            "programming error was silently converted to UNAVAILABLE"
        )
