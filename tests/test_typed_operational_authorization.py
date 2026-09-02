import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from holosim.proof_authority_boundary import build_bounded_proof
from holosim.collector import Collector
from holosim.core import HoloChain
from holosim.service import HoloService
from holosim.typed_operational_authorization import (
    ACTION_SERVICE_APPEND,
    OperationalAuthorizationError,
    build_operational_authorization,
    validate_operational_authorization,
)


TARGET = hashlib.sha256(b"target").hexdigest()


def _authorization(**overrides):
    values = {
        "authorization_id": "approval:append-1",
        "actor_id": "external-reviewer",
        "action": ACTION_SERVICE_APPEND,
        "target_sha256": TARGET,
        "approval_reference": "approval:append-1",
    }
    values.update(overrides)
    return build_operational_authorization(**values)


def _service_authorization():
    canonical = json.dumps(
        "target", sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return _authorization(
        target_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    )


def test_authorization_is_typed_target_bound_and_non_epistemic():
    authorization = _authorization()

    assert validate_operational_authorization(
        authorization,
        expected_action=ACTION_SERVICE_APPEND,
        expected_target_sha256=TARGET,
    )
    assert authorization["write_authority"] == "EXACT_TARGET_ONLY"
    assert authorization["truth_claimed"] is False
    assert authorization["execution_authority"] == "NONE"


def test_bare_digest_cannot_be_relabelled_as_approval_reference():
    with pytest.raises(OperationalAuthorizationError, match="bare proof"):
        _authorization(approval_reference="a" * 64)


def test_wrong_target_and_tampering_are_rejected():
    authorization = _authorization()
    with pytest.raises(OperationalAuthorizationError, match="target does not match"):
        validate_operational_authorization(
            authorization,
            expected_action=ACTION_SERVICE_APPEND,
            expected_target_sha256="b" * 64,
        )

    authorization["actor_id"] = "different-reviewer"
    with pytest.raises(OperationalAuthorizationError, match="identity is invalid"):
        validate_operational_authorization(
            authorization,
            expected_action=ACTION_SERVICE_APPEND,
            expected_target_sha256=TARGET,
        )


def test_proof_object_cannot_authorize_service_append(tmp_path):
    proof = build_bounded_proof(
        proof_id="proof-1",
        claim_id="claim-1",
        claim="bounded claim",
        assumptions=["declared assumption"],
        method={"name": "declared"},
        scope={"target": "bounded"},
        evidence_bindings=[{"evidence_id": "e-1", "evidence_sha256": "a" * 64}],
        conclusion="supported under boundary",
        limitations=[],
    )

    chain_path = tmp_path / "chain.jsonl"
    result = HoloService(chain_path).append("target", authorization=proof)

    assert result["status"] == "BLOCKED"
    assert result["commit_performed"] is False
    assert result["write_authority"] == "NONE"
    assert not chain_path.exists()


def test_proof_digest_cannot_authorize_through_collector_adapter(tmp_path):
    chain_path = tmp_path / "chain.jsonl"

    result = Collector(chain_path).collect_text(
        "candidate",
        force=True,
        reviewer="external-reviewer",
        approval_reference="a" * 64,
    )

    assert result["status"] == "blocked"
    assert result["append"]["commit_performed"] is False
    assert not chain_path.exists()


def test_authorization_is_consumed_once_and_survives_restart(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    authorization = _service_authorization()

    first = HoloService(chain_path).append("target", authorization=authorization)
    replay = HoloService(chain_path).append("target", authorization=authorization)

    assert first["status"] == "COMMITTED"
    assert replay["status"] == "BLOCKED"
    assert replay["reason"] == "authorization has already been consumed"
    assert len(chain_path.read_text(encoding="utf-8").splitlines()) == 1


def test_failed_attempt_does_not_consume_authorization(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    authorization = _service_authorization()

    failed = HoloService(chain_path).append("wrong target", authorization=authorization)
    committed = HoloService(chain_path).append("target", authorization=authorization)

    assert failed["status"] == "BLOCKED"
    assert committed["status"] == "COMMITTED"


def test_authorization_id_cannot_be_reissued_with_a_new_hash(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    first_authorization = _service_authorization()
    reissued = build_operational_authorization(
        authorization_id=first_authorization["authorization_id"],
        actor_id="different-reviewer",
        action=ACTION_SERVICE_APPEND,
        target_sha256=first_authorization["target_sha256"],
        approval_reference=first_authorization["approval_reference"],
    )

    first = HoloService(chain_path).append(
        "target", authorization=first_authorization,
    )
    replay = HoloService(chain_path).append("target", authorization=reissued)

    assert first["status"] == "COMMITTED"
    assert replay["status"] == "BLOCKED"
    assert len(chain_path.read_text(encoding="utf-8").splitlines()) == 1


def test_concurrent_replay_commits_exactly_once(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    authorization = _service_authorization()

    def attempt(_):
        return HoloService(chain_path).append("target", authorization=authorization)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))

    assert sorted(result["status"] for result in results) == ["BLOCKED", "COMMITTED"]
    lines = chain_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = HoloChain(chain_path).get_state()[0]
    assert payload["operational_authorization"]["authorization_hash"] == (
        authorization["authorization_hash"]
    )
