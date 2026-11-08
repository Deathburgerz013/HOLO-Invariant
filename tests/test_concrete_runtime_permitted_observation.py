"""Integration tests for permitted observations and runtime comparisons."""

from holosim.hook_contract import build_hook_request
from holosim.observation_permit import (
    observation_root_sha256,
    run_permitted_aligned_observation,
)
from holosim.signed_occurrence import build_signed_occurrence


SECRET = b"p" * 32
OBSERVED_AT = "2026-08-04T12:30:00-07:00"


def _request():
    return build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference="state.txt",
        payload={"encoding": "utf-8"},
    )


def _candidate(request):
    return {
        "candidate_id": "read-current-state",
        "request": request,
        "evidence_references": ["evidence:current-environment"],
        "rule_references": ["invariant:bounded-observation"],
        "comparison_status": "SUPPORTED",
        "uncertainty": "LOW",
        "unresolved_conflicts": [],
        "value": 5,
        "cost": 1,
        "urgency": 0,
        "dependency_impact": 0,
    }


def _permit(root, request, occurrence_id):
    return build_signed_occurrence(
        source_id="operator",
        occurrence_id=occurrence_id,
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(root),
            "not_before": "2026-08-04T12:00:00-07:00",
            "not_after": "2026-08-04T13:00:00-07:00",
        },
        observed_at="2026-08-04T11:59:00-07:00",
        sequence=1,
        nonce=f"nonce:{occurrence_id}",
        secret=SECRET,
    )


def _observe(root, request, permit, *, seen=None):
    return run_permitted_aligned_observation(
        goal_reference="goal:observe-current-state",
        reference_state="state:before-observation",
        candidates=[_candidate(request)],
        allowed_root=root,
        observed_at=OBSERVED_AT,
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set() if seen is None else seen,
        permit_registry_path=root / "permits.sqlite3",
    )


def test_permitted_observation_matches_actual_file(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"5")
    request = _request()

    result = _controlled(
        tmp_path,
        request,
        _permit(tmp_path, request, "permit-1"),
    )

    assert result.decision == "OBSERVED"
    assert result.classification == "SUPPORTED"
    assert result.evidence_valid is True
    assert result.permit_verified is True
    assert result.observation_performed is True
    assert result.accepted is False
    assert result.write_authority == "NONE"
    assert result.execution_authority == "NONE"


def test_new_observation_detects_environmental_change(tmp_path):
    target = tmp_path / "state.txt"
    target.write_bytes(b"5")
    request = _request()

    first = _controlled(
        tmp_path,
        request,
        _permit(tmp_path, request, "permit-first"),
    )

    target.write_bytes(b"7")

    second = _controlled(
        tmp_path,
        request,
        _permit(tmp_path, request, "permit-second"),
    )

    assert first.classification == "SUPPORTED"
    assert second.classification == "CONTRADICTED"
    assert first.result_hash != second.result_hash
    assert first.permit_verified is True
    assert second.permit_verified is True
    assert second.accepted is False


def test_missing_file_cannot_support_expected_state(tmp_path):
    request = _request()

    result = _controlled(
        tmp_path,
        request,
        _permit(tmp_path, request, "permit-missing"),
    )

    assert result.decision == "OBSERVED"
    assert result.classification == "UNAVAILABLE"
    assert result.evidence_valid is False
    assert result.permit_verified is True
    assert result.observation_performed is True


def test_invalid_permit_does_not_observe_file(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"5")
    request = _request()
    permit = _permit(tmp_path, request, "permit-invalid")

    run = _observe(
        tmp_path,
        request,
        permit,
        seen={"permit-invalid"},
    )

    assert run["decision"] == "HALT_UNPERMITTED"
    assert run["observation_performed"] is False
    assert run["observation_result"] is None
    assert run["accepted"] is False
    assert run["execution_authority"] == "NONE"


from holosim.concrete_runtime import run_concrete_permitted_observation


def _controlled(root, request, permit, *, seen=None, observed_at=OBSERVED_AT):
    return run_concrete_permitted_observation(
        goal_reference="goal:observe-current-state",
        reference_state="state:before-observation",
        candidates=[_candidate(request)],
        allowed_root=root,
        observed_at=observed_at,
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set() if seen is None else seen,
        permit_registry_path=root / "permits.sqlite3",
        expected_content="5",
    )


def test_controlled_observation_supports_matching_file(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"5")
    request = _request()

    result = _controlled(
        tmp_path, request, _permit(tmp_path, request, "controlled-valid")
    )

    assert result.classification == "SUPPORTED"
    assert result.evidence_valid is True
    assert result.permit_verified is True
    assert result.observation_performed is True
    assert result.accepted is False
    assert result.execution_authority == "NONE"


def test_controlled_observation_rejects_replayed_permit(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"5")
    request = _request()
    permit = _permit(tmp_path, request, "controlled-replay")

    result = _controlled(
        tmp_path, request, permit, seen={"controlled-replay"}
    )

    assert result.decision == "HALT_UNPERMITTED"
    assert result.classification == "UNAVAILABLE"
    assert result.observation_performed is False


def test_controlled_observation_rejects_expired_permit(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"5")
    request = _request()

    result = _controlled(
        tmp_path,
        request,
        _permit(tmp_path, request, "controlled-expired"),
        observed_at="2026-08-04T13:00:01-07:00",
    )

    assert result.decision == "HALT_UNPERMITTED"
    assert result.classification == "UNAVAILABLE"
    assert result.observation_performed is False


def test_controlled_observation_rejects_wrong_root(tmp_path):
    allowed = tmp_path / "allowed"
    other = tmp_path / "other"
    allowed.mkdir()
    other.mkdir()
    (allowed / "state.txt").write_bytes(b"5")
    request = _request()

    result = _controlled(
        allowed,
        request,
        _permit(other, request, "controlled-wrong-root"),
    )

    assert result.decision == "HALT_UNPERMITTED"
    assert result.classification == "UNAVAILABLE"
    assert result.observation_performed is False


def test_controlled_observation_detects_changed_content(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"7")
    request = _request()

    result = _controlled(
        tmp_path, request, _permit(tmp_path, request, "controlled-changed")
    )

    assert result.classification == "CONTRADICTED"
    assert result.evidence_valid is True
    assert result.permit_verified is True
    assert result.execution_authority == "NONE"


def test_invalid_expected_content_does_not_consume_permit(tmp_path):
    import holosim.concrete_runtime as runtime

    (tmp_path / "state.txt").write_bytes(b"5")
    request = _request()
    permit = _permit(tmp_path, request, "invalid-expected")

    arguments = {
        "goal_reference": "goal:observe-current-state",
        "reference_state": "state:before-observation",
        "candidates": [_candidate(request)],
        "allowed_root": tmp_path,
        "observed_at": OBSERVED_AT,
        "permit_occurrence": permit,
        "permit_source_secrets": {"operator": SECRET},
        "seen_occurrence_ids": set(),
        "permit_registry_path": tmp_path / "permits.sqlite3",
    }

    invalid = runtime.run_concrete_permitted_observation(
        **arguments,
        expected_content=5,
    )

    assert invalid.decision == "HALT_INVALID_INPUT"
    assert invalid.classification == "UNAVAILABLE"
    assert invalid.evidence_valid is False
    assert invalid.permit_verified is False
    assert invalid.observation_performed is False
    assert invalid.accepted is False
    assert invalid.write_authority == "NONE"
    assert invalid.execution_authority == "NONE"

    valid = runtime.run_concrete_permitted_observation(
        **arguments,
        expected_content="5",
    )

    assert valid.classification == "SUPPORTED"
    assert valid.permit_verified is True
    assert valid.observation_performed is True


def test_synthetic_comparison_entry_point_is_absent():
    import holosim.concrete_runtime as runtime

    assert not hasattr(runtime, "_compare_reported_observation")
