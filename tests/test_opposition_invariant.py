import pytest

from holosim.opposition_invariant import evaluate_opposition


def test_opposed_states_share_one_declared_dimension():
    result = evaluate_opposition(dimension="direction", left="left", right="right")
    assert result["dimension"] == "direction"
    assert result["left"] == "left"
    assert result["right"] == "right"
    assert result["distinguishable"] is True


def test_same_state_is_not_an_opposition():
    result = evaluate_opposition(dimension="direction", left="left", right="left")
    assert result["distinguishable"] is False


def test_dimension_cannot_change_mid_comparison():
    with pytest.raises(ValueError):
        evaluate_opposition(dimension="direction", left="left", right="solid", right_dimension="phase")


def test_empty_dimension_fails_closed():
    with pytest.raises(ValueError):
        evaluate_opposition(dimension="", left="left", right="right")


def test_observation_does_not_claim_universal_oppositeness():
    result = evaluate_opposition(dimension="occupancy", left="occupied", right="unoccupied")
    assert result["universal_claim"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_distinguishable_states_do_not_automatically_establish_opposition():
    result = evaluate_opposition(dimension="direction", left="left", right="forward")
    assert result["distinguishable"] is True
    assert result["opposite"] is False
    assert result["relation_verified"] is False


def test_declared_opposition_requires_symmetric_relation():
    result = evaluate_opposition(dimension="direction", left="left", right="right", oppositions={"left":"right","right":"left"})
    assert result["opposite"] is True
    assert result["relation_verified"] is True


def test_one_way_relation_does_not_establish_opposition():
    result = evaluate_opposition(dimension="direction", left="left", right="right", oppositions={"left":"right"})
    assert result["opposite"] is False
    assert result["relation_verified"] is False


def test_opposition_cannot_escape_declared_domain():
    result = evaluate_opposition(dimension="direction", left="left", right="banana", oppositions={"left":"banana","banana":"left"}, domain={"left","right","forward","backward"})
    assert result["opposite"] is False
    assert result["relation_verified"] is False


def test_unpaired_state_remains_unresolved_within_fixed_domain():
    domain = {"negative","zero","positive"}
    oppositions = {"negative":"positive","positive":"negative"}
    result = evaluate_opposition(dimension="sign", left="zero", right="positive", oppositions=oppositions, domain=domain)
    assert result["distinguishable"] is True
    assert result["opposite"] is False
    assert result["relation_verified"] is False


def test_fixed_point_can_be_self_inverse_without_being_distinguishable():
    domain = {"negative","zero","positive"}
    oppositions = {"negative":"positive","zero":"zero","positive":"negative"}
    result = evaluate_opposition(dimension="sign", left="zero", right="zero", oppositions=oppositions, domain=domain)
    assert result["distinguishable"] is False
    assert result["relation_verified"] is True
    assert result["opposite"] is True
