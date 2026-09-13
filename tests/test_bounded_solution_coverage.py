from holosim.bounded_solution_coverage import compare_solution_coverage


def test_tracks_newly_solved_preserved_regressed_and_unresolved_conditions() -> None:
    before = {
        "T1": False,
        "T2": True,
        "T3": False,
        "T4": True,
    }
    after = {
        "T1": True,
        "T2": False,
        "T3": True,
        "T4": True,
    }

    result = compare_solution_coverage(
        before=before,
        after=after,
    )

    assert result["newly_solved"] == ["T1", "T3"]
    assert result["preserved"] == ["T4"]
    assert result["regressed"] == ["T2"]
    assert result["unresolved"] == []
    assert result["before_solved_count"] == 2
    assert result["after_solved_count"] == 3
    assert result["net_solved_gain"] == 1
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
def test_positive_net_gain_does_not_hide_regression() -> None:
    result = compare_solution_coverage(
        before={
            "T1": False,
            "T2": True,
            "T3": False,
            "T4": True,
        },
        after={
            "T1": True,
            "T2": False,
            "T3": True,
            "T4": True,
        },
    )

    assert result["net_solved_gain"] == 1
    assert result["regressed"] == ["T2"]
def test_regression_prevents_closure_even_when_nothing_is_unresolved() -> None:
    result = compare_solution_coverage(
        before={
            "T1": False,
            "T2": True,
            "T3": False,
            "T4": True,
        },
        after={
            "T1": True,
            "T2": False,
            "T3": True,
            "T4": True,
        },
    )

    assert result["unresolved"] == []
    assert result["regressed"] == ["T2"]
    assert result["closure_ready"] is False
def test_all_conditions_solved_without_regression_is_closure_ready() -> None:
    result = compare_solution_coverage(
        before={
            "T1": False,
            "T2": True,
            "T3": False,
            "T4": True,
        },
        after={
            "T1": True,
            "T2": True,
            "T3": True,
            "T4": True,
        },
    )

    assert result["newly_solved"] == ["T1", "T3"]
    assert result["preserved"] == ["T2", "T4"]
    assert result["regressed"] == []
    assert result["unresolved"] == []
    assert result["closure_ready"] is True
def test_condition_identity_must_match_between_runs() -> None:
    try:
        compare_solution_coverage(
            before={
                "T1": False,
                "T2": True,
            },
            after={
                "T1": True,
                "T3": True,
            },
        )
    except ValueError as exc:
        assert str(exc) == "before and after must contain the same condition ids"
    else:
        raise AssertionError("mismatched condition ids were accepted")
def test_empty_condition_set_cannot_claim_closure() -> None:
    result = compare_solution_coverage(
        before={},
        after={},
    )

    assert result["before_solved_count"] == 0
    assert result["after_solved_count"] == 0
    assert result["closure_ready"] is False
def test_unresolved_condition_prevents_closure_without_regression() -> None:
    result = compare_solution_coverage(
        before={
            "T1": False,
            "T2": True,
        },
        after={
            "T1": False,
            "T2": True,
        },
    )

    assert result["regressed"] == []
    assert result["unresolved"] == ["T1"]
    assert result["closure_ready"] is False
def test_condition_outcomes_must_be_booleans() -> None:
    try:
        compare_solution_coverage(
            before={
                "T1": False,
                "T2": True,
            },
            after={
                "T1": True,
                "T2": 1,
            },
        )
    except ValueError as exc:
        assert str(exc) == "condition outcomes must be booleans"
    else:
        raise AssertionError("non-boolean condition outcome was accepted")
