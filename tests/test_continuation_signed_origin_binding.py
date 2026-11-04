"""Regression tests for coherent continuation substitution and signed origin."""

import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from holosim.canonical import stable_hash
from holosim.operator_resume_handoff import (
    build_operator_resume_handoff,
    resume_operator_handoff,
)
from holosim.pinned_origin_checkpoint import verify_origin_with_pinned_policy
from holosim.portable_verified_reentry import build_portable_reentry_bundle
from holosim.reconstructor import build_reconstructed_state
from holosim.signed_origin_checkpoint import sign_origin_checkpoint
from holosim.spine_admission import build_spine_admission_receipt
from holosim.verified_cold_start_reentry_gateway import (
    build_verified_cold_start_reentry_packet,
)
from tests.test_signed_origin_checkpoint import _candidate


OLD_RULE = "For this experiment, transform x using (x * 90) + 72."
NEW_RULE = "For this experiment, transform x using (x * 91) + 73."

HANDOFF_PATH = (
    Path(__file__).resolve().parents[1]
    / "continuation-fresh-handoff.json"
)


def replace_rule(value):
    if isinstance(value, str):
        return value.replace(OLD_RULE, NEW_RULE)
    if isinstance(value, list):
        return [replace_rule(item) for item in value]
    if isinstance(value, dict):
        return {
            key: replace_rule(item)
            for key, item in value.items()
        }
    return value


def build_pair():
    original = json.loads(HANDOFF_PATH.read_text(encoding="utf-8"))
    bundle = original["portable_bundle"]
    packet = bundle["packet"]

    source_items = copy.deepcopy(bundle["source_items"])
    assert OLD_RULE in json.dumps(source_items)

    replacement_items = replace_rule(source_items)
    assert OLD_RULE not in json.dumps(replacement_items)
    assert NEW_RULE in json.dumps(replacement_items)

    prior_state = packet["reconstructed_state"]

    state = build_reconstructed_state(
        reference=prior_state["reference"],
        target_ids=prior_state["target_ids"],
        items=replacement_items,
    )

    replacement_packet = build_verified_cold_start_reentry_packet(
        packet_id=packet["packet_id"],
        reconstructed_state=state,
        source_items=replacement_items,
        head_check=packet["head_check"],
        conflicts=packet["conflicts"],
    )

    replacement_bundle = build_portable_reentry_bundle(
        bundle_id=bundle["bundle_id"],
        packet=replacement_packet,
        source_items=replacement_items,
    )

    replacement = build_operator_resume_handoff(
        handoff_id=original["handoff_id"],
        portable_bundle=replacement_bundle,
        objective=original["objective"],
        completed=original["completed"],
        constraints=original["constraints"],
        unresolved=original["unresolved"],
        next_action=original["next_action"],
        baseline_restart_steps=original[
            "restart_cost"
        ]["baseline_operator_steps"],
    )

    for handoff in (original, replacement):
        replay = resume_operator_handoff(handoff)

        assert replay["working_state"]["status"] == "COMPLETE"
        assert replay["working_state"]["missing_ids"] == []
        assert handoff["handoff_hash"] == stable_hash({
            key: value
            for key, value in handoff.items()
            if key != "handoff_hash"
        })
        assert handoff["accepted"] is False
        assert handoff["write_authority"] == "NONE"
        assert handoff["execution_authority"] == "NONE"

    assert original["handoff_hash"] != replacement["handoff_hash"]

    return original, replacement


def candidate_for(handoff):
    template = _candidate()
    assert template.count(b"commit:abc") == 1

    candidate = template.replace(
        b"commit:abc",
        f"handoff-sha256:{handoff['handoff_hash']}".encode("ascii"),
    )

    receipt = build_spine_admission_receipt(
        candidate.decode("utf-8"),
        validator_id="idx:v1",
        contributor_id=None,
    )

    assert receipt["decision"] == "ADMITTED"
    assert receipt["accepted_as_truth"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

    return candidate


def candidate_matches_handoff(candidate, handoff):
    """Explicit comparison, not a claim about signed-origin verifier integration."""
    expected_reference = (
        f"handoff-sha256:{handoff['handoff_hash']}".encode("ascii")
    )
    template = _candidate()
    assert template.count(b"commit:abc") == 1

    expected_candidate = template.replace(
        b"commit:abc",
        expected_reference,
    )
    return candidate == expected_candidate


def make_key(folder, name):
    key = folder / name

    subprocess.run(
        [
            "ssh-keygen", "-q", "-t", "ed25519",
            "-N", "", "-f", str(key),
        ],
        check=True,
        capture_output=True,
    )

    policy = folder / f"{name}.allowed"
    policy.write_text(
        "anchor "
        + key.with_suffix(".pub").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return key, policy


def test_both_coherent_handoffs_reconstruct():
    original, replacement = build_pair()

    assert candidate_for(original) != candidate_for(replacement)


def test_signed_origin_rejects_coherent_substitution(tmp_path):
    if shutil.which("ssh-keygen") is None:
        pytest.skip("OpenSSH ssh-keygen unavailable")

    original, replacement = build_pair()

    original_candidate = candidate_for(original)
    replacement_candidate = candidate_for(replacement)

    legitimate_key, legitimate_policy = make_key(
        tmp_path, "legitimate"
    )
    attacker_key, attacker_policy = make_key(
        tmp_path, "attacker"
    )

    original_pin = hashlib.sha256(
        legitimate_policy.read_bytes()
    ).hexdigest()

    original_checkpoint = sign_origin_checkpoint(
        candidate=original_candidate,
        validator_id="idx:v1",
        contributor_id=None,
        signer_identity="anchor",
        private_key_path=legitimate_key,
    )

    attacker_checkpoint = sign_origin_checkpoint(
        candidate=replacement_candidate,
        validator_id="idx:v1",
        contributor_id=None,
        signer_identity="anchor",
        private_key_path=attacker_key,
    )

    def verify(candidate, checkpoint, policy):
        return verify_origin_with_pinned_policy(
            candidate=candidate,
            checkpoint=checkpoint,
            allowed_signers_path=policy,
            expected_policy_sha256=original_pin,
        )

    scenarios = [
        (
            original_candidate,
            original_checkpoint,
            legitimate_policy,
            "VERIFIED",
        ),
        (
            replacement_candidate,
            original_checkpoint,
            legitimate_policy,
            "REJECTED_BINDING",
        ),
        (
            replacement_candidate,
            attacker_checkpoint,
            legitimate_policy,
            "REJECTED_SIGNATURE",
        ),
        (
            replacement_candidate,
            attacker_checkpoint,
            attacker_policy,
            "REJECTED_POLICY",
        ),
    ]

    for candidate, checkpoint, policy, expected in scenarios:
        result = verify(candidate, checkpoint, policy)

        assert result["status"] == expected
        assert result["accepted"] is False
        assert result["write_authority"] == "NONE"
        assert result["execution_authority"] == "NONE"
        assert result["policy_custody_verified"] is False


def test_signed_candidate_reference_cannot_match_replacement():
    original, replacement = build_pair()

    original_candidate = candidate_for(original)
    replacement_candidate = candidate_for(replacement)

    assert candidate_matches_handoff(
        original_candidate, original
    )
    assert candidate_matches_handoff(
        replacement_candidate, replacement
    )

    assert not candidate_matches_handoff(
        original_candidate, replacement
    )
    assert not candidate_matches_handoff(
        replacement_candidate, original
    )
