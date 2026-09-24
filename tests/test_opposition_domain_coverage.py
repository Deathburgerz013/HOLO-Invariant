from holosim.opposition_invariant import evaluate_domain_coverage


def test_complete_domain_coverage_accepts_pairs_and_fixed_points():
    result = evaluate_domain_coverage(
        dimension="sign",
        domain={"negative", "zero", "positive"},
        oppositions={"negative": "positive", "zero": "zero", "positive": "negative"},
    )
    assert result["covered"] == {"negative", "zero", "positive"}
    assert result["unresolved"] == set()
    assert result["coverage_complete"] is True


def test_unpaired_member_remains_explicitly_unresolved():
    result = evaluate_domain_coverage(
        dimension="sign",
        domain={"negative", "zero", "positive"},
        oppositions={"negative": "positive", "positive": "negative"},
    )
    assert result["covered"] == {"negative", "positive"}
    assert result["unresolved"] == {"zero"}
    assert result["coverage_complete"] is False


def test_asymmetric_mapping_does_not_count_as_coverage():
    result = evaluate_domain_coverage(
        dimension="direction",
        domain={"left", "right"},
        oppositions={"left": "right"},
    )
    assert result["covered"] == set()
    assert result["unresolved"] == {"left", "right"}
    assert result["coverage_complete"] is False


def test_external_partner_does_not_count_as_domain_coverage():
    result = evaluate_domain_coverage(
        dimension="direction",
        domain={"left", "right"},
        oppositions={"left": "banana", "banana": "left", "right": "right"},
    )
    assert result["covered"] == {"right"}
    assert result["unresolved"] == {"left"}
    assert result["coverage_complete"] is False
    assert result["universal_claim"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_complete_coverage_does_not_establish_relation_truth():
    result = evaluate_domain_coverage(dimension="arbitrary", domain={"cat","refrigerator"}, oppositions={"cat":"refrigerator","refrigerator":"cat"})
    assert result["coverage_complete"] is True
    assert result["universal_claim"] is False
    assert result["accepted"] is False
