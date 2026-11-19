
"""Measure observation invocation across the existing permit boundary."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from holosim.hook_contract import build_hook_request
from holosim.observation_permit import (
    observation_root_sha256,
    run_permitted_aligned_observation,
)
from holosim.signed_occurrence import build_signed_occurrence


SECRET = b"p" * 32
OBSERVED_AT = "2026-08-04T12:30:00-07:00"


def make_request():
    return build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference="state.txt",
        payload={"encoding": "utf-8"},
    )


def make_candidate(request):
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


def make_permit(tmp_path, request):
    return build_signed_occurrence(
        source_id="operator",
        occurrence_id="permit-boundary-1",
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(tmp_path),
            "not_before": "2026-08-04T12:00:00-07:00",
            "not_after": "2026-08-04T13:00:00-07:00",
        },
        observed_at="2026-08-04T11:59:00-07:00",
        sequence=1,
        nonce="nonce:permit-boundary-1",
        secret=SECRET,
    )


def run(tmp_path, request, permit):
    return run_permitted_aligned_observation(
        goal_reference="goal:observe-current-state",
        reference_state="state:before-observation",
        candidates=[make_candidate(request)],
        allowed_root=tmp_path,
        observed_at=OBSERVED_AT,
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set(),
        permit_registry_path=tmp_path / "permits.sqlite3",
    )


@pytest.mark.parametrize(
    ("condition", "expected_calls"),
    [
        ("invalid_signature", 0),
        ("valid_unused", 1),
        ("consumed", 1),
    ],
)
def test_permit_boundary_controls_observation_invocation(
    tmp_path, condition, expected_calls
):
    (tmp_path / "state.txt").write_text("state", encoding="utf-8")
    request = make_request()
    permit = make_permit(tmp_path, request)

    if condition == "invalid_signature":
        permit = deepcopy(permit)
        permit["payload"]["not_after"] = "2099-01-01T00:00:00+00:00"

    from holosim.observation_permit import execute_observation

    with patch(
        "holosim.observation_permit.execute_observation",
        wraps=execute_observation,
    ) as observer:
        if condition == "consumed":
            first = run(tmp_path, request, permit)
            assert first["decision"] == "OBSERVED"

        result = run(tmp_path, request, permit)

        assert observer.call_count == expected_calls

    if condition == "valid_unused":
        assert result["decision"] == "OBSERVED"
        assert result["observation_performed"] is True
    else:
        assert result["decision"] == "HALT_UNPERMITTED"
        assert result["observation_performed"] is False

    assert result["accepted"] is False
    assert result["execution_authority"] == "NONE"
