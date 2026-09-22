from holosim.functional_consciousness_experiment import (
    FunctionalConsciousnessExperimentError,
)


def notice(observation, *, prior_notice=None):
    return {
        "observation": observation,
        "prior_notice": prior_notice,
        "noticed": True,
    }


def carry_notice(state, notice_record):
    if not notice_record["noticed"]:
        raise FunctionalConsciousnessExperimentError(
            "notice must be explicitly established"
        )

    return {
        **state,
        "carried_notice": notice_record,
    }


def reencounter(state, observation):
    carried = state.get("carried_notice")

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


def test_notice_is_distinct_from_observation():
    record = notice("red")

    assert record["observation"] == "red"
    assert record["noticed"] is True


def test_notice_can_be_carried_forward():
    state = carry_notice({}, notice("red"))

    assert state["carried_notice"]["observation"] == "red"


def test_carried_notice_changes_later_processing():
    state = carry_notice({}, notice("red"))
    result = reencounter(state, "red")

    assert result["recognition"] is True


def test_without_carried_notice_reencounter_has_no_recognition():
    result = reencounter({}, "red")

    assert result["recognition"] is False


def test_different_observation_creates_difference():
    state = carry_notice({}, notice("red"))
    result = reencounter(state, "blue")

    assert result["recognition"] is False

def reconstruct_instance(state):
    return {
        "carried_notice": state.get("carried_notice"),
    }


def test_notice_survives_instance_reconstruction():
    instance_a = carry_notice({}, notice("red"))
    instance_b = reconstruct_instance(instance_a)
    result = reencounter(instance_b, "red")
    assert result["recognition"] is True


def test_reconstruction_without_notice_does_not_recognize():
    instance_a = carry_notice({}, notice("red"))
    stripped = {"carried_notice": None}
    instance_b = reconstruct_instance(stripped)
    result = reencounter(instance_b, "red")
    assert result["recognition"] is False


def test_same_observation_without_prior_notice_is_not_recognition():
    instance_b = reconstruct_instance({})
    result = reencounter(instance_b, "red")
    assert result["recognition"] is False


def test_reconstructed_notice_changes_later_processing():
    instance_a = carry_notice({}, notice("red"))
    instance_b = reconstruct_instance(instance_a)
    first = reencounter(instance_b, "red")
    second = reencounter(instance_b, "blue")
    assert first["recognition"] is True
    assert second["recognition"] is False
def make_notice_receipt(notice_record):
    return {
        "type": "notice_receipt",
        "observation": notice_record["observation"],
        "noticed": notice_record["noticed"],
    }


def reconstruct_notice_from_receipt(receipt):
    if receipt["type"] != "notice_receipt":
        raise ValueError("invalid notice receipt")

    return {
        "observation": receipt["observation"],
        "noticed": receipt["noticed"],
    }


def test_notice_can_be_reconstructed_from_evidence_receipt():
    instance_a = carry_notice({}, notice("red"))
    receipt = make_notice_receipt(instance_a["carried_notice"])

    instance_b = reconstruct_notice_from_receipt(receipt)
    result = reencounter(
        {"carried_notice": instance_b},
        "red",
    )

    assert result["recognition"] is True


def test_raw_observation_without_notice_does_not_reconstruct_notice():
    receipt = {
        "type": "observation_receipt",
        "observation": "red",
    }

    try:
        reconstruct_notice_from_receipt(receipt)
    except (KeyError, ValueError):
        pass
    else:
        raise AssertionError("raw observation must not reconstruct notice")


def test_removing_notice_evidence_prevents_reconstruction():
    instance_a = carry_notice({}, notice("red"))
    receipt = make_notice_receipt(instance_a["carried_notice"])
    del receipt["noticed"]

    try:
        reconstruct_notice_from_receipt(receipt)
    except (KeyError, ValueError):
        pass
    else:
        raise AssertionError("missing notice evidence must fail close")



def test_reconstructed_notice_is_distinct_from_raw_observation():
    instance_a = carry_notice({}, notice("red"))
    receipt = make_notice_receipt(instance_a["carried_notice"])

    reconstructed = reconstruct_notice_from_receipt(receipt)

    assert reconstructed["noticed"] is True
    assert reconstructed["observation"] == "red"


def test_notice_survives_verified_reconstruction():
    from holosim.reconstructor import build_reconstructed_state, validate_reconstructed_state

    notice_item = {
        "id": "notice-red",
        "observation": "red",
        "noticed": True,
    }
    target = {
        "id": "reentry-target",
        "requires": ["notice-red"],
    }
    sources = [notice_item, target]

    state = build_reconstructed_state("carry-notice", ["reentry-target"], sources)

    validate_reconstructed_state(state, sources)

    carried = state["carried_items"]
    notice = next(item for item in carried if item["id"] == "notice-red")
    result = reencounter({"carried_notice": notice}, "red")

    assert notice["noticed"] is True
    assert result["recognition"] is True

    # the reconstructed state must carry the exact notice item
    assert notice in carried
