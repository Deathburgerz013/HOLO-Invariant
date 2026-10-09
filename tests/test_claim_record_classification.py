from holosim.core import HoloChain


def test_service_append_is_not_classified_as_original_claim(tmp_path):
    chain = HoloChain(tmp_path / "classification.jsonl")

    original = chain.append({"claim": "A testable observation"})
    operational = chain.append({
        "type": "service_append",
        "source": "HoloService",
        "content": "Operational event",
    })

    claims = chain.get_claim_index()

    assert len(chain.load_and_verify()) == 2
    assert [claim["idx"] for claim in claims] == [original["idx"]]
    assert operational["idx"] not in {
        claim["idx"] for claim in claims
    }
