from holosim.functional_consciousness_experiment import (
    FunctionalConsciousnessExperimentError,
)


def registration(observation, *, prior_registration=None):
    return {
        "observation": observation,
        "prior_registration": prior_registration,
        "registered": True,
    }


def carry_registration(state, registration_record):
    if not registration_record["registered"]:
        raise FunctionalConsciousnessExperimentError(
            "registration must be explicitly established"
        )

    return {
        **state,
        "carried_registration": registration_record,
    }


def reencounter(state, observation):
    carried = state.get("carried_registration")

    if carried is None:
        return {
            **state,
            "recognition": False,
            "current_observation": observation,
        }

    return {
        **state,
        "current_observation": observation,
        "recognition": (
            carried["observation"] == observation
        ),
    }


def test_registration_is_distinct_from_observation():
    record = registration("red")

    assert record["observation"] == "red"
    assert record["registered"] is True


def test_registration_can_be_carried_forward():
    state = carry_registration({}, registration("red"))

    assert state["carried_registration"]["observation"] == "red"


def test_carried_registration_changes_later_processing():
    state = carry_registration({}, registration("red"))
    result = reencounter(state, "red")

    assert result["recognition"] is True


def test_without_carried_registration_reencounter_has_no_recognition():
    result = reencounter({}, "red")

    assert result["recognition"] is False


def test_different_observation_creates_difference():
    state = carry_registration({}, registration("red"))
    result = reencounter(state, "blue")

    assert result["recognition"] is False

def reconstruct_instance(state):
    return {
        "carried_registration": state.get("carried_registration"),
    }


def test_registration_survives_instance_reconstruction():
    instance_a = carry_registration({}, registration("red"))
    instance_b = reconstruct_instance(instance_a)
    result = reencounter(instance_b, "red")
    assert result["recognition"] is True


def test_reconstruction_without_registration_does_not_recognize():
    instance_a = carry_registration({}, registration("red"))
    stripped = {"carried_registration": None}
    instance_b = reconstruct_instance(stripped)
    result = reencounter(instance_b, "red")
    assert result["recognition"] is False


def test_same_observation_without_prior_registration_is_not_recognition():
    instance_b = reconstruct_instance({})
    result = reencounter(instance_b, "red")
    assert result["recognition"] is False


def test_reconstructed_registration_changes_later_processing():
    instance_a = carry_registration({}, registration("red"))
    instance_b = reconstruct_instance(instance_a)
    first = reencounter(instance_b, "red")
    second = reencounter(instance_b, "blue")
    assert first["recognition"] is True
    assert second["recognition"] is False
def make_registration_receipt(registration_record):
    return {
        "type": "registration_receipt",
        "observation": registration_record["observation"],
        "registered": registration_record["registered"],
    }


def reconstruct_registration_from_receipt(receipt):
    if receipt["type"] != "registration_receipt":
        raise ValueError("invalid registration receipt")

    return {
        "observation": receipt["observation"],
        "registered": receipt["registered"],
    }


def test_registration_can_be_reconstructed_from_evidence_receipt():
    instance_a = carry_registration({}, registration("red"))
    receipt = make_registration_receipt(instance_a["carried_registration"])

    instance_b = reconstruct_registration_from_receipt(receipt)
    result = reencounter(
        {"carried_registration": instance_b},
        "red",
    )

    assert result["recognition"] is True


def test_raw_observation_without_registration_does_not_reconstruct_registration():
    receipt = {
        "type": "observation_receipt",
        "observation": "red",
    }

    try:
        reconstruct_registration_from_receipt(receipt)
    except (KeyError, ValueError):
        pass
    else:
        raise AssertionError("raw observation must not reconstruct registration")


def test_removing_registration_evidence_prevents_reconstruction():
    instance_a = carry_registration({}, registration("red"))
    receipt = make_registration_receipt(instance_a["carried_registration"])
    del receipt["registered"]

    try:
        reconstruct_registration_from_receipt(receipt)
    except (KeyError, ValueError):
        pass
    else:
        raise AssertionError("missing registration evidence must fail close")



def test_reconstructed_registration_is_distinct_from_raw_observation():
    instance_a = carry_registration({}, registration("red"))
    receipt = make_registration_receipt(instance_a["carried_registration"])

    reconstructed = reconstruct_registration_from_receipt(receipt)

    assert reconstructed["registered"] is True
    assert reconstructed["observation"] == "red"


def test_registration_survives_verified_reconstruction():
    from holosim.reconstructor import build_reconstructed_state, validate_reconstructed_state

    registration_item = {
        "id": "registration-red",
        "observation": "red",
        "registered": True,
    }
    target = {
        "id": "reentry-target",
        "requires": ["registration-red"],
    }
    sources = [registration_item, target]

    state = build_reconstructed_state("carry-registration", ["reentry-target"], sources)

    validate_reconstructed_state(state, sources)

    carried = state["carried_items"]
    registration = next(item for item in carried if item["id"] == "registration-red")
    result = reencounter({"carried_registration": registration}, "red")

    assert registration["registered"] is True
    assert result["recognition"] is True

    # the reconstructed state must carry the exact registration item
    assert registration in carried
