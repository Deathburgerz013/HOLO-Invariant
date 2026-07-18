import hashlib
import json

import pytest

import holosim.embeddings as embeddings
from holosim.embeddings import (
    IngestionReceiptError,
    check_ingestion_receipt_current,
    compute_similarity,
    compute_similarity_observation,
    evaluate_ingestion,
    should_ingest,
)


def force_token_overlap(monkeypatch):
    monkeypatch.setattr(embeddings, "_sentence_similarity", lambda left, right: None)
    monkeypatch.setattr(embeddings, "_sklearn_similarity", lambda left, right: None)


def rehash(receipt):
    body = dict(receipt)
    body.pop("receipt_hash", None)
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    receipt["receipt_hash"] = hashlib.sha256(encoded).hexdigest()


def observation(score, backend="token_overlap", version="1", model=None):
    return {
        "score": score,
        "backend": backend,
        "backend_version": version,
        "model_identity": model,
    }


def test_existing_similarity_api_remains_compatible(monkeypatch):
    force_token_overlap(monkeypatch)

    assert compute_similarity("alpha beta", "alpha beta") == 1.0
    assert compute_similarity("alpha", "omega") == 0.0
    assert should_ingest("alpha beta", ["alpha beta"], threshold=0.85) is False
    assert should_ingest("new signal", ["alpha beta"], threshold=0.85) is True


def test_similarity_observation_names_the_backend(monkeypatch):
    force_token_overlap(monkeypatch)

    result = compute_similarity_observation("alpha beta", "alpha gamma")

    assert result == {
        "score": pytest.approx(1 / 3),
        "backend": "token_overlap",
        "backend_version": "1",
        "model_identity": None,
    }


def test_identical_content_is_rejected_with_bound_receipt(monkeypatch):
    force_token_overlap(monkeypatch)

    receipt = evaluate_ingestion(
        "same durable object",
        ["same durable object"],
        threshold=0.85,
    )

    assert receipt["candidate_sha256"] == hashlib.sha256(
        b"same durable object"
    ).hexdigest()
    assert receipt["recent_entry_hashes"] == [receipt["candidate_sha256"]]
    assert receipt["best_match_sha256"] == receipt["candidate_sha256"]
    assert receipt["best_score"] == 1.0
    assert receipt["should_ingest"] is False
    assert receipt["reason"] == "SIMILAR_TO_EXISTING"
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert len(receipt["receipt_hash"]) == 64


def test_novel_content_is_accepted_as_selection_only(monkeypatch):
    force_token_overlap(monkeypatch)

    receipt = evaluate_ingestion("new signal", ["old artifact"], threshold=0.85)

    assert receipt["best_score"] == 0.0
    assert receipt["should_ingest"] is True
    assert receipt["reason"] == "NOVEL"
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert "does not establish truth" in receipt["interpretation_notice"]


def test_empty_comparison_window_is_novel_without_inventing_backend():
    receipt = evaluate_ingestion("first object", [])

    assert receipt["comparisons"] == []
    assert receipt["recent_entry_hashes"] == []
    assert receipt["best_match_sha256"] is None
    assert receipt["best_score"] == 0.0
    assert receipt["should_ingest"] is True


def test_threshold_boundary_is_inclusive(monkeypatch):
    monkeypatch.setattr(
        embeddings,
        "compute_similarity_observation",
        lambda left, right: observation(0.85),
    )

    receipt = evaluate_ingestion("candidate", ["existing"], threshold=0.85)

    assert receipt["best_score"] == 0.85
    assert receipt["should_ingest"] is False


@pytest.mark.parametrize("score", [float("nan"), float("inf"), 1.1, -1.1, True])
def test_invalid_backend_score_fails_closed(monkeypatch, score):
    monkeypatch.setattr(
        embeddings,
        "compute_similarity_observation",
        lambda left, right: observation(score),
    )

    with pytest.raises(IngestionReceiptError, match="similarity score"):
        evaluate_ingestion("candidate", ["existing"])


def test_receipt_is_current_when_every_binding_is_unchanged(monkeypatch):
    force_token_overlap(monkeypatch)
    entries = ["alpha", "beta"]
    receipt = evaluate_ingestion("gamma", entries, threshold=0.85, recent_window=2)

    assert check_ingestion_receipt_current(
        receipt,
        "gamma",
        entries,
        threshold=0.85,
        recent_window=2,
    ) == {"current": True, "stale_reason": None}


def test_candidate_change_stales_prior_receipt(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate-v1", ["existing"])

    assert check_ingestion_receipt_current(
        receipt, "candidate-v2", ["existing"]
    ) == {"current": False, "stale_reason": "CANDIDATE_CHANGED"}


@pytest.mark.parametrize(
    "changed_entries",
    [
        ["first", "replacement"],
        ["second", "first"],
        ["first"],
    ],
)
def test_comparison_window_change_stales_prior_receipt(
    monkeypatch, changed_entries
):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion(
        "candidate", ["first", "second"], recent_window=2
    )

    assert check_ingestion_receipt_current(
        receipt, "candidate", changed_entries, recent_window=2
    ) == {"current": False, "stale_reason": "COMPARISON_WINDOW_CHANGED"}


@pytest.mark.parametrize(
    ("threshold", "recent_window"),
    [(0.5, 2), (0.85, 1)],
)
def test_config_change_stales_prior_receipt(
    monkeypatch, threshold, recent_window
):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion(
        "candidate", ["first", "second"], threshold=0.85, recent_window=2
    )

    assert check_ingestion_receipt_current(
        receipt,
        "candidate",
        ["first", "second"],
        threshold=threshold,
        recent_window=recent_window,
    ) == {"current": False, "stale_reason": "CONFIG_CHANGED"}


def test_backend_change_stales_prior_receipt(monkeypatch):
    monkeypatch.setattr(
        embeddings,
        "compute_similarity_observation",
        lambda left, right: observation(0.2, backend="token_overlap", version="1"),
    )
    receipt = evaluate_ingestion("candidate", ["existing"])
    monkeypatch.setattr(
        embeddings,
        "compute_similarity_observation",
        lambda left, right: observation(
            0.2,
            backend="sentence_transformers",
            version="3.4.1",
            model="all-MiniLM-L6-v2",
        ),
    )

    assert check_ingestion_receipt_current(
        receipt, "candidate", ["existing"]
    ) == {"current": False, "stale_reason": "ENVIRONMENT_CHANGED"}


def test_score_change_under_same_backend_stales_observation(monkeypatch):
    monkeypatch.setattr(
        embeddings,
        "compute_similarity_observation",
        lambda left, right: observation(0.2),
    )
    receipt = evaluate_ingestion("candidate", ["existing"])
    monkeypatch.setattr(
        embeddings,
        "compute_similarity_observation",
        lambda left, right: observation(0.3),
    )

    assert check_ingestion_receipt_current(
        receipt, "candidate", ["existing"]
    ) == {"current": False, "stale_reason": "OBSERVATION_CHANGED"}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("accepted", True, "cannot grant acceptance"),
        ("write_authority", "ALL", "cannot grant write authority"),
    ],
)
def test_rehashed_authority_tampering_fails_closed(
    monkeypatch, field, value, message
):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    receipt[field] = value
    rehash(receipt)

    with pytest.raises(IngestionReceiptError, match=message):
        check_ingestion_receipt_current(receipt, "candidate", ["existing"])


def test_unrehashed_tampering_fails_integrity(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    receipt["should_ingest"] = not receipt["should_ingest"]

    with pytest.raises(IngestionReceiptError, match="hash mismatch"):
        check_ingestion_receipt_current(receipt, "candidate", ["existing"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.pop("reason"),
        lambda receipt: receipt.update(
            reason=(
                "SIMILAR_TO_EXISTING"
                if receipt["reason"] == "NOVEL"
                else "NOVEL"
            )
        ),
        lambda receipt: receipt.update(best_score=-0.5),
        lambda receipt: receipt.update(best_match_sha256=None),
        lambda receipt: receipt.update(current=False, stale_reason="FORGED"),
        lambda receipt: receipt["comparisons"][0].update(window_index=9),
        lambda receipt: receipt["comparisons"][0].update(entry_sha256="0" * 64),
        lambda receipt: receipt["comparisons"][0].update(score=1.0),
        lambda receipt: receipt["comparisons"][0].pop("backend"),
    ],
)
def test_rehashed_semantically_invalid_receipt_fails_closed(
    monkeypatch, mutate
):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    mutate(receipt)
    rehash(receipt)

    with pytest.raises(IngestionReceiptError):
        check_ingestion_receipt_current(receipt, "candidate", ["existing"])


def test_malformed_comparison_cannot_bypass_validation_on_earlier_stale_path(
    monkeypatch,
):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    receipt["comparisons"] = "not-a-list"
    rehash(receipt)

    with pytest.raises(IngestionReceiptError, match="comparisons"):
        check_ingestion_receipt_current(
            receipt,
            "changed-candidate",
            ["changed-entry"],
            threshold=0.5,
        )


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_nonfinite_receipt_value_fails_with_domain_error(monkeypatch, bad_value):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    receipt["best_score"] = bad_value

    with pytest.raises(IngestionReceiptError, match="finite"):
        check_ingestion_receipt_current(receipt, "candidate", ["existing"])


def test_cyclic_receipt_fails_with_domain_error(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    receipt["cycle"] = receipt

    with pytest.raises(IngestionReceiptError, match="cycles"):
        check_ingestion_receipt_current(receipt, "candidate", ["existing"])


def test_excessively_deep_receipt_fails_with_domain_error(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    nested = []
    cursor = nested
    for _ in range(10):
        child = []
        cursor.append(child)
        cursor = child
    receipt["deep"] = nested

    with pytest.raises(IngestionReceiptError, match="depth"):
        check_ingestion_receipt_current(receipt, "candidate", ["existing"])


def test_boolean_cannot_impersonate_receipt_version(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    receipt["version"] = True
    rehash(receipt)

    with pytest.raises(IngestionReceiptError, match="version"):
        check_ingestion_receipt_current(receipt, "candidate", ["existing"])


def test_boolean_cannot_impersonate_comparison_index(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["first", "second"])
    receipt["comparisons"][1]["window_index"] = True
    rehash(receipt)

    with pytest.raises(IngestionReceiptError, match="indexes"):
        check_ingestion_receipt_current(
            receipt, "changed-candidate", ["changed-entry"]
        )


def test_comparison_count_cannot_exceed_declared_window(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion(
        "candidate", ["first", "second"], recent_window=2
    )
    receipt["recent_window"] = 1
    rehash(receipt)

    with pytest.raises(IngestionReceiptError, match="exceeds recent_window"):
        check_ingestion_receipt_current(
            receipt, "changed-candidate", ["changed-entry"]
        )


def test_oversized_threshold_fails_with_domain_error():
    with pytest.raises(IngestionReceiptError, match="threshold"):
        evaluate_ingestion("candidate", [], threshold=10**10000)


def test_oversized_backend_score_fails_with_domain_error(monkeypatch):
    monkeypatch.setattr(
        embeddings,
        "compute_similarity_observation",
        lambda left, right: observation(10**10000),
    )

    with pytest.raises(IngestionReceiptError, match="similarity score"):
        evaluate_ingestion("candidate", ["existing"])


@pytest.mark.parametrize("field", ["threshold", "comparison_score"])
def test_rehashed_oversized_integer_cannot_bypass_on_stale_path(
    monkeypatch, field
):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    if field == "threshold":
        receipt["threshold"] = 10**400
    else:
        receipt["comparisons"][0]["score"] = 10**400
    rehash(receipt)

    with pytest.raises(IngestionReceiptError, match="finite number"):
        check_ingestion_receipt_current(
            receipt, "changed-candidate", ["changed-entry"]
        )


def test_oversized_evaluation_window_fails_with_domain_error():
    with pytest.raises(IngestionReceiptError, match="recent_window"):
        evaluate_ingestion("candidate", [], recent_window=10**10000)


def test_oversized_currentness_window_fails_with_domain_error(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])

    with pytest.raises(IngestionReceiptError, match="recent_window"):
        check_ingestion_receipt_current(
            receipt,
            "changed-candidate",
            ["changed-entry"],
            recent_window=10**10000,
        )


def test_rehashed_oversized_stored_window_fails_before_stale_path(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    receipt["recent_window"] = 10**400
    rehash(receipt)

    with pytest.raises(IngestionReceiptError, match="recent_window"):
        check_ingestion_receipt_current(
            receipt, "changed-candidate", ["changed-entry"]
        )


def test_exact_negative_one_score_selects_a_valid_best_match(monkeypatch):
    monkeypatch.setattr(
        embeddings,
        "compute_similarity_observation",
        lambda left, right: observation(-1.0),
    )
    receipt = evaluate_ingestion("candidate", ["existing"])

    assert receipt["best_score"] == -1.0
    assert receipt["best_match_sha256"] == receipt["recent_entry_hashes"][0]
    assert check_ingestion_receipt_current(
        receipt, "candidate", ["existing"]
    ) == {"current": True, "stale_reason": None}


@pytest.mark.parametrize(
    ("candidate", "entries"),
    [("\ud800", []), ("candidate", ["\ud800"])],
)
def test_surrogate_input_text_fails_with_domain_error(
    monkeypatch, candidate, entries
):
    force_token_overlap(monkeypatch)

    with pytest.raises(IngestionReceiptError, match="UTF-8"):
        evaluate_ingestion(candidate, entries)


def test_surrogate_stored_receipt_string_fails_before_stale_path(monkeypatch):
    force_token_overlap(monkeypatch)
    receipt = evaluate_ingestion("candidate", ["existing"])
    receipt["interpretation_notice"] = "\ud800"

    with pytest.raises(IngestionReceiptError, match="UTF-8"):
        check_ingestion_receipt_current(
            receipt, "changed-candidate", ["changed-entry"]
        )


class HostileString(str):
    def lower(self):
        raise RuntimeError("hostile lower")

    def encode(self, *args, **kwargs):
        raise RuntimeError("hostile encode")


class HostileEntry:
    def __str__(self):
        raise RuntimeError("hostile str")


@pytest.mark.parametrize("operation", ["evaluate", "currentness"])
def test_string_subclass_candidate_fails_with_domain_error(
    monkeypatch, operation
):
    force_token_overlap(monkeypatch)
    hostile = HostileString("candidate")

    with pytest.raises(IngestionReceiptError, match="plain string"):
        if operation == "evaluate":
            evaluate_ingestion(hostile, ["existing"])
        else:
            receipt = evaluate_ingestion("candidate", ["existing"])
            check_ingestion_receipt_current(
                receipt, hostile, ["existing"]
            )


def test_failing_entry_string_conversion_uses_domain_error(monkeypatch):
    force_token_overlap(monkeypatch)

    with pytest.raises(IngestionReceiptError, match="converted to text"):
        evaluate_ingestion("candidate", [HostileEntry()])


@pytest.mark.parametrize("operation", ["evaluate", "currentness"])
def test_noniterable_entry_collection_uses_domain_error(monkeypatch, operation):
    force_token_overlap(monkeypatch)

    with pytest.raises(IngestionReceiptError, match="existing_entries"):
        if operation == "evaluate":
            evaluate_ingestion("candidate", None)
        else:
            receipt = evaluate_ingestion("candidate", ["existing"])
            check_ingestion_receipt_current(receipt, "candidate", None)


@pytest.mark.parametrize(
    ("threshold", "recent_window", "message"),
    [
        (float("nan"), 100, "finite number"),
        (1.1, 100, "finite number"),
        (True, 100, "finite number"),
        (0.85, 0, "positive integer"),
        (0.85, True, "positive integer"),
    ],
)
def test_invalid_configuration_fails_closed(
    threshold, recent_window, message
):
    with pytest.raises(IngestionReceiptError, match=message):
        evaluate_ingestion(
            "candidate",
            [],
            threshold=threshold,
            recent_window=recent_window,
        )


def test_evaluation_does_not_mutate_candidate_collection(monkeypatch):
    force_token_overlap(monkeypatch)
    entries = [{"content": "first"}, {"content": "second"}]
    before = [dict(entry) for entry in entries]

    evaluate_ingestion("candidate", entries)

    assert entries == before
