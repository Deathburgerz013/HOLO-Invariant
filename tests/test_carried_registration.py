from holosim.carried_registration import (
    CarriedRegistrationError,
    evaluate_verified_carried_registration,
)
from holosim.reconstructor import (
    build_reconstructed_state,
    validate_reconstructed_state,
)


def _state_with_registration():
    sources = [
        {
            "id": "registration-red",
            "requires": [],
            "observation": "red",
            "registered": True,
        },
        {
            "id": "target",
            "requires": ["registration-red"],
            "value": "reencounter",
        },
    ]

    state = build_reconstructed_state(
        "carried-registration",
        ["target"],
        sources,
    )

    validate_reconstructed_state(state, sources)
    return state, sources


def _state_without_registration():
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
        "carried-registration-control",
        ["target"],
        sources,
    )

    validate_reconstructed_state(state, sources)
    return state, sources


def test_carried_registration_recognizes_matching_reencounter():
    state, sources = _state_with_registration()

    result = evaluate_verified_carried_registration(
        state,
        sources,
        "red",
    )

    assert result["prior_registration_present"] is True
    assert result["observation_matches_prior_registration"] is True
    assert result["recognized"] is True


def test_carried_registration_rejects_different_observation():
    state, sources = _state_with_registration()

    result = evaluate_verified_carried_registration(
        state,
        sources,
        "blue",
    )

    assert result["prior_registration_present"] is True
    assert result["observation_matches_prior_registration"] is False
    assert result["recognized"] is False


def test_same_observation_without_registration_is_not_recognized():
    state, sources = _state_without_registration()

    result = evaluate_verified_carried_registration(
        state,
        sources,
        "red",
    )

    assert result["prior_registration_present"] is False
    assert result["observation_matches_prior_registration"] is False
    assert result["recognized"] is False


def test_result_grants_no_authority():
    state, sources = _state_with_registration()

    result = evaluate_verified_carried_registration(
        state,
        sources,
        "red",
    )

    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_invalid_reconstructed_state_fails_closed():
    state, sources = _state_with_registration()
    state["state_hash"] = "0" * 64

    try:
        evaluate_verified_carried_registration(state, sources, "red")
    except CarriedRegistrationError:
        pass
    else:
        raise AssertionError("invalid reconstructed state must fail closed")