from holosim.opposition_invariant import evaluate_involution


def test_negation_reproduces_sign_opposition():
    result = evaluate_involution(domain={-1, 0, 1}, transform=lambda value: -value)
    assert result["pairs"] == {(-1, 1), (0, 0), (1, -1)}
    assert result["unresolved"] == set()
    assert result["involution_complete"] is True


def test_transform_that_escapes_domain_remains_unresolved():
    result = evaluate_involution(domain={0, 1}, transform=lambda value: value + 1)
    assert result["involution_complete"] is False
    assert result["unresolved"] == {0, 1}


def test_transform_must_return_to_original_state():
    result = evaluate_involution(domain={0, 1, 2}, transform=lambda value: (value + 1) % 3)
    assert result["involution_complete"] is False
    assert result["unresolved"] == {0, 1, 2}


def test_involution_does_not_claim_universal_opposition():
    result = evaluate_involution(domain={False, True}, transform=lambda value: not value)
    assert result["involution_complete"] is True
    assert result["universal_claim"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_transform_failure_remains_unresolved():
    def transform(value):
        if value == 1:
            raise ValueError("undefined")
        return value
    result = evaluate_involution(domain={0,1}, transform=transform)
    assert result["pairs"] == {(0,0)}
    assert result["unresolved"] == {1}
    assert result["involution_complete"] is False
