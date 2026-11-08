"""Tests for host-owned permitted observation configuration."""

from datetime import datetime, timezone
import inspect

import pytest

from holosim.hook_contract import build_hook_request
from holosim.observation_permit import observation_root_sha256
from holosim.permitted_observation_host import PermittedObservationHost
from holosim.signed_occurrence import build_signed_occurrence


SECRET = b"p" * 32
NOW = datetime(2026, 8, 4, 19, 30, tzinfo=timezone.utc)


def make_host(tmp_path, **overrides):
    config = {
        "permit_registry_path": tmp_path.parent / (tmp_path.name + "-permits.sqlite3"),
        "allowed_root": tmp_path,
        "source_secrets": {"operator": SECRET},
        "clock": lambda: NOW,
    }
    config.update(overrides)
    return PermittedObservationHost(**config)


def make_request_and_candidate():
    request = build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference="state.txt",
        payload={"encoding": "utf-8"},
    )
    candidate = {
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
    return request, candidate


def make_permit(root, request, *, secret=SECRET, occurrence_id="host-test"):
    return build_signed_occurrence(
        source_id="operator",
        occurrence_id=occurrence_id,
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(root),
            "not_before": "2026-08-04T19:00:00+00:00",
            "not_after": "2026-08-04T20:00:00+00:00",
        },
        observed_at="2026-08-04T18:59:00+00:00",
        sequence=1,
        nonce=f"nonce:{occurrence_id}",
        secret=secret,
    )


def observe(host, candidate, permit):
    return host.observe(
        goal_reference="goal:observe-current-state",
        reference_state="state:before-observation",
        candidates=[candidate],
        permit_occurrence=permit,
        expected_content="5",
    )


def test_host_does_not_expose_trusted_overrides():
    parameters = inspect.signature(PermittedObservationHost.observe).parameters

    for forbidden in (
        "permit_registry_path",
        "allowed_root",
        "observed_at",
        "permit_source_secrets",
        "seen_occurrence_ids",
        "clock",
    ):
        assert forbidden not in parameters


def test_host_observes_then_rejects_replay(tmp_path):
    (tmp_path / "state.txt").write_text("5", encoding="utf-8")
    request, candidate = make_request_and_candidate()
    permit = make_permit(tmp_path, request)

    host = make_host(tmp_path)

    first = observe(host, candidate, permit)
    second = observe(host, candidate, permit)

    assert first.decision == "OBSERVED"
    assert first.evidence_valid is True
    assert first.observation_performed is True

    assert second.decision == "HALT_UNPERMITTED"
    assert second.observation_performed is False


def test_host_rejects_untrusted_signing_key(tmp_path):
    (tmp_path / "state.txt").write_text("5", encoding="utf-8")
    request, candidate = make_request_and_candidate()

    forged = make_permit(
        tmp_path,
        request,
        secret=b"f" * 32,
        occurrence_id="forged",
    )

    result = observe(make_host(tmp_path), candidate, forged)

    assert result.decision == "HALT_UNPERMITTED"
    assert result.observation_performed is False


def test_host_rejects_permit_for_other_root(tmp_path):
    (tmp_path / "state.txt").write_text("5", encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()

    request, candidate = make_request_and_candidate()
    permit = make_permit(other, request, occurrence_id="wrong-root")

    result = observe(make_host(tmp_path), candidate, permit)

    assert result.decision == "HALT_UNPERMITTED"
    assert result.observation_performed is False


def test_host_uses_its_clock_not_permit_timestamp(tmp_path):
    (tmp_path / "state.txt").write_text("5", encoding="utf-8")
    request, candidate = make_request_and_candidate()
    permit = make_permit(tmp_path, request, occurrence_id="expired")

    future = datetime(2026, 8, 5, 19, 30, tzinfo=timezone.utc)
    host = make_host(tmp_path, clock=lambda: future)

    result = observe(host, candidate, permit)

    assert result.decision == "HALT_UNPERMITTED"
    assert result.observation_performed is False


def test_host_rejects_naive_clock(tmp_path):
    host = make_host(
        tmp_path,
        clock=lambda: datetime(2026, 8, 4, 19, 30),
    )

    with pytest.raises(ValueError, match="aware"):
        host.observe(
            goal_reference="goal",
            reference_state="state",
            candidates=[],
            permit_occurrence={},
            expected_content="5",
        )


def test_host_requires_absolute_registry(tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        make_host(
            tmp_path,
            permit_registry_path="relative/permits.sqlite3",
        )


def test_host_requires_trusted_source(tmp_path):
    with pytest.raises(ValueError, match="trusted source"):
        make_host(tmp_path, source_secrets={})


def test_host_copies_source_secret_mapping(tmp_path):
    (tmp_path / "state.txt").write_text("5", encoding="utf-8")

    source_secrets = {"operator": SECRET}
    host = make_host(tmp_path, source_secrets=source_secrets)

    source_secrets["operator"] = b"f" * 32

    request, candidate = make_request_and_candidate()
    permit = make_permit(
        tmp_path,
        request,
        occurrence_id="copied-secret",
    )

    result = observe(host, candidate, permit)

    assert result.decision == "OBSERVED"
    assert result.observation_performed is True


def test_reconstructed_host_rejects_consumed_permit(tmp_path):
    (tmp_path / "state.txt").write_text("5", encoding="utf-8")

    request, candidate = make_request_and_candidate()
    permit = make_permit(
        tmp_path,
        request,
        occurrence_id="reconstructed-host",
    )

    first = observe(make_host(tmp_path), candidate, permit)
    second = observe(make_host(tmp_path), candidate, permit)

    assert first.decision == "OBSERVED"
    assert second.decision == "HALT_UNPERMITTED"
    assert second.observation_performed is False


def test_host_rejects_registry_inside_observation_root(tmp_path):
    with pytest.raises(
        ValueError,
        match="permit registry must be outside the observation root",
    ):
        make_host(
            tmp_path,
            permit_registry_path=tmp_path / "permits.sqlite3",
        )
