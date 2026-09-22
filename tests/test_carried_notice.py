from holosim.carried_notice import (
    CarriedNoticeError,
    evaluate_carried_notice,
)
from holosim.reconstructor import (
    build_reconstructed_state,
    validate_reconstructed_state,
)


def _state_with_notice():
    sources = [
        {
            "id": "notice-red",
            "requires": [],
            "observation": "red",
            "noticed": True,
        },
        {
            "id": "target",
            "requires": ["notice-red"],
            "value": "reencounter",
        },
    ]

    state = build_reconstructed_state(
        "carried-notice",
        ["target"],
        sources,
    )

    validate_reconstructed_state(state, sources)
    return state, sources


def _state_without_notice():
    sources = [
        {
            "id": "observation-red",
            "requires": [],
            "observation": "red",
        },
        {
            "id": "target",
            "requires": ["observation-red"],
            "value": "reencounter",
        },
    ]

    state = build_reconstructed_state(
        "carried-notice-control",
        ["target"],
        sources,
    )

    validate_reconstructed_state(state, sources)
    return state, sources


def test_carried_notice_recognizes_matching_reencounter():
    state, sources = _state_with_notice()

    result = evaluate_carried_notice(
        state,
        sources,
        "red",
    )

    assert result["prior_notice_present"] is True
    assert result["observation_matches_prior_notice"] is True
    assert result["recognized"] is True


def test_carried_notice_rejects_different_observation():
    state, sources = _state_with_notice()

    result = evaluate_carried_notice(
        state,
        sources,
        "blue",
    )

    assert result["prior_notice_present"] is True
    assert result["observation_matches_prior_notice"] is False
    assert result["recognized"] is False


def test_same_observation_without_notice_is_not_recognized():
    state, sources = _state_without_notice()

    result = evaluate_carried_notice(
        state,
        sources,
        "red",
    )

    assert result["prior_notice_present"] is False
    assert result["observation_matches_prior_notice"] is False
    assert result["recognized"] is False


def test_result_grants_no_authority():
    state, sources = _state_with_notice()

    result = evaluate_carried_notice(
        state,
        sources,
        "red",
    )

    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_invalid_reconstructed_state_fails_closed():
    state, sources = _state_with_notice()
    state["state_hash"] = "0" * 64

    try:
        evaluate_carried_notice(state, sources, "red")
    except CarriedNoticeError:
        pass
    else:
        raise AssertionError("invalid reconstructed state must fail closed")