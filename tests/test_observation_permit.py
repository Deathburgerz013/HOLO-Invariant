from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.hook_contract import build_hook_request
from holosim.observation_permit import (
    ObservationPermitError,
    observation_root_sha256,
    run_permitted_aligned_observation,
)
from holosim.signed_occurrence import build_signed_occurrence


SECRET = b"p" * 32


def _request(reference: str = "state.txt") -> dict:
    return build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference=reference,
        payload={"encoding": "utf-8"},
    )


def _candidate(request: dict, *, value: float = 5, cost: float = 1) -> dict:
    return {
        "candidate_id": "read-current-state",
        "request": request,
        "evidence_references": ["evidence:current-environment"],
        "rule_references": ["invariant:bounded-observation"],
        "comparison_status": "SUPPORTED",
        "uncertainty": "LOW",
        "unresolved_conflicts": [],
        "value": value,
        "cost": cost,
        "urgency": 0,
        "dependency_impact": 0,
    }


def _permit(
    tmp_path,
    request: dict,
    *,
    source_id: str = "operator",
    occurrence_id: str = "permit-1",
    request_hash: str | None = None,
    root_hash: str | None = None,
    not_before: str = "2026-08-04T12:00:00-07:00",
    not_after: str = "2026-08-04T13:00:00-07:00",
) -> dict:
    return build_signed_occurrence(
        source_id=source_id,
        occurrence_id=occurrence_id,
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request_hash or request["request_hash"],
            "allowed_root_sha256": root_hash or observation_root_sha256(tmp_path),
            "not_before": not_before,
            "not_after": not_after,
        },
        observed_at="2026-08-04T11:59:00-07:00",
        sequence=1,
        nonce=f"nonce:{occurrence_id}",
        secret=SECRET,
    )


def _run(tmp_path, request: dict, permit: dict, **overrides) -> dict:
    arguments = {
        "goal_reference": "goal:observe-current-state",
        "reference_state": "state:before-observation",
        "candidates": [_candidate(request)],
        "allowed_root": tmp_path,
        "observed_at": "2026-08-04T12:30:00-07:00",
        "permit_occurrence": permit,
        "permit_source_secrets": {"operator": SECRET},
        "seen_occurrence_ids": set(),
    }
    arguments.update(overrides)
    return run_permitted_aligned_observation(**arguments)


def test_matching_signed_permit_allows_one_bounded_observation(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"current state")
    request = _request()

    result = _run(tmp_path, request, _permit(tmp_path, request))

    assert result["decision"] == "OBSERVED"
    assert result["observation_performed"] is True
    assert result["observation_result"]["evidence"]["content"] == "current state"
    assert result["permit_verification"]["status"] == "VERIFIED"
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize(
    ("observed_at", "expected_reason"),
    [
        ("2026-08-04T11:59:59-07:00", "permit is not active yet"),
        ("2026-08-04T13:00:01-07:00", "permit has expired"),
    ],
)
def test_observation_outside_permitted_time_window_halts(
    tmp_path,
    observed_at,
    expected_reason,
):
    (tmp_path / "state.txt").write_bytes(b"state")
    request = _request()

    result = _run(
        tmp_path,
        request,
        _permit(tmp_path, request),
        observed_at=observed_at,
    )

    assert result["decision"] == "HALT_UNPERMITTED"
    assert result["reason"] == expected_reason
    assert result["observation_performed"] is False
    assert result["observation_result"] is None


def test_permit_for_different_request_halts_without_reading(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"state")
    request = _request()
    other_request = _request("other.txt")

    result = _run(tmp_path, request, _permit(tmp_path, other_request))

    assert result["decision"] == "HALT_UNPERMITTED"
    assert result["reason"] == "permit is bound to a different request"
    assert result["observation_performed"] is False


def test_permit_for_different_root_halts_without_reading(tmp_path):
    allowed = tmp_path / "allowed"
    other = tmp_path / "other"
    allowed.mkdir()
    other.mkdir()
    (allowed / "state.txt").write_bytes(b"state")
    request = _request()
    permit = _permit(
        allowed,
        request,
        root_hash=observation_root_sha256(other),
    )

    result = _run(allowed, request, permit)

    assert result["decision"] == "HALT_UNPERMITTED"
    assert result["reason"] == "permit is bound to a different allowed root"
    assert result["observation_performed"] is False


def test_unknown_permit_source_halts_without_reading(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"state")
    request = _request()
    permit = _permit(tmp_path, request, source_id="unknown")

    result = _run(tmp_path, request, permit)

    assert result["decision"] == "HALT_UNPERMITTED"
    assert result["reason"] == "REJECTED_UNKNOWN_SOURCE"
    assert result["observation_performed"] is False


def test_replayed_permit_halts_without_reading(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"state")
    request = _request()
    permit = _permit(tmp_path, request)

    result = _run(
        tmp_path,
        request,
        permit,
        seen_occurrence_ids={permit["occurrence_id"]},
    )

    assert result["decision"] == "HALT_UNPERMITTED"
    assert result["reason"] == "REJECTED_REPLAY"
    assert result["observation_performed"] is False


def test_tampered_permit_halts_without_reading(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"state")
    request = _request()
    permit = _permit(tmp_path, request)
    permit["payload"]["not_after"] = "2099-01-01T00:00:00+00:00"

    result = _run(tmp_path, request, permit)

    assert result["decision"] == "HALT_UNPERMITTED"
    assert result["reason"] == "REJECTED_TAMPERED"
    assert result["observation_performed"] is False


def test_inverted_permit_window_is_rejected(tmp_path):
    request = _request()
    permit = _permit(
        tmp_path,
        request,
        not_before="2026-08-04T14:00:00-07:00",
        not_after="2026-08-04T13:00:00-07:00",
    )

    with pytest.raises(ObservationPermitError, match="time window is inverted"):
        _run(tmp_path, request, permit)


def test_unaligned_selection_halts_before_permit_use(tmp_path):
    request = _request()
    permit = _permit(tmp_path, request)

    result = run_permitted_aligned_observation(
        goal_reference="goal:observe-current-state",
        reference_state="state:before-observation",
        candidates=[_candidate(request, value=1, cost=5)],
        allowed_root=tmp_path,
        observed_at="2026-08-04T12:30:00-07:00",
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set(),
    )

    assert result["decision"] == "HALT_UNALIGNED"
    assert result["permit_verification"] is None
    assert result["observation_performed"] is False


def test_inputs_are_not_mutated(tmp_path):
    (tmp_path / "state.txt").write_bytes(b"state")
    request = _request()
    permit = _permit(tmp_path, request)
    candidate = _candidate(request)
    candidate_before = deepcopy(candidate)
    permit_before = deepcopy(permit)

    run_permitted_aligned_observation(
        goal_reference="goal:observe-current-state",
        reference_state="state:before-observation",
        candidates=[candidate],
        allowed_root=tmp_path,
        observed_at="2026-08-04T12:30:00-07:00",
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set(),
    )

    assert candidate == candidate_before
    assert permit == permit_before
