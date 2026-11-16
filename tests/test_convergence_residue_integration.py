import json
import subprocess
import sys
from copy import deepcopy

import pytest
from holosim.canonical import stable_hash
from holosim.auditable_residue_verifier import build_auditable_residue_verifier
from holosim.software_convergence_entrypoint import run_software_convergence_request
from test_software_convergence_entrypoint import REQUEST, _decomposer, _comparator, _proposer, _capability_verifier, _project_verifier

@pytest.mark.parametrize(("change", "expected_status", "expected_reason"), [
    ("preserved", "CONVERGED", "AUDITABLE_RESIDUE_VERIFIED"),
    ("omitted", "RESIDUE_VERIFICATION_FAILED", "RECORDED_CONTRADICTION_OMITTED"),
    ("rewritten", "RESIDUE_VERIFICATION_FAILED", "RECORDED_CONTRADICTION_REWRITTEN"),
])
def test_real_residue_verifier_gates_convergence(tmp_path, change, expected_status, expected_reason):
    contradiction = {"id": "calculator-original-failure", "field": "calculator.add(2, 3)", "observed_values": [-1, 5]}
    preserved = {"state": {"requirement": "add must return the sum"}, "contradictions": [contradiction]}
    reconstructed = deepcopy(preserved)
    if change == "omitted":
        reconstructed["contradictions"] = []
    elif change == "rewritten":
        reconstructed["contradictions"][0]["observed_values"] = [5]
    receipt = run_software_convergence_request(
        REQUEST, tmp_path, _decomposer, _comparator, _proposer,
        _capability_verifier, _project_verifier,
        residue_verifier=build_auditable_residue_verifier(),
        preserved_record=preserved,
        reconstructed_state=reconstructed,
    )
    residue = receipt["residue_verification"]
    assert receipt["final_verification"]["passed"] is True
    assert receipt["status"] == expected_status
    assert receipt["converged"] is (change == "preserved")
    assert receipt["runnable"] is (change == "preserved")
    assert residue["reason"] == expected_reason
    assert residue["verified"] is (change == "preserved")
    assert residue["continuity_claimed"] is False
    assert residue["execution_authority"] == "NONE"
    for result in (receipt, residue):
        assert result["accepted"] is False
        assert result["truth_claimed"] is False
        assert result["write_authority"] == "NONE"
        body = {key: value for key, value in result.items() if key != "receipt_hash"}
        assert result["receipt_hash"] == stable_hash(body)


@pytest.mark.parametrize(("change", "expected_status"), [
    ("preserved", "CONVERGED"),
    ("omitted", "RESIDUE_VERIFICATION_FAILED"),
    ("rewritten", "RESIDUE_VERIFICATION_FAILED"),
])
def test_fresh_process_residue_gates_convergence(tmp_path, change, expected_status):
    contradiction = {"id": "calculator-original-failure", "field": "calculator.add(2, 3)", "observed_values": [-1, 5]}
    preserved = {"state": {"requirement": "add must return the sum"}, "contradictions": [contradiction]}
    record_path = tmp_path / "residue.json"
    record_path.write_text(json.dumps(preserved, sort_keys=True), encoding="utf-8")
    if change == "omitted":
        altered = deepcopy(preserved)
        altered["contradictions"] = []
        record_path.write_text(json.dumps(altered, sort_keys=True), encoding="utf-8")
    elif change == "rewritten":
        altered = deepcopy(preserved)
        altered["contradictions"][0]["observed_values"] = [5]
        record_path.write_text(json.dumps(altered, sort_keys=True), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-c", "import json,sys; print(json.dumps(json.load(open(sys.argv[1], encoding='utf-8'))))", str(record_path)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    assert completed.returncode == 0, completed.stderr
    reconstructed = json.loads(completed.stdout)
    receipt = run_software_convergence_request(
        REQUEST, tmp_path, _decomposer, _comparator, _proposer,
        _capability_verifier, _project_verifier,
        residue_verifier=build_auditable_residue_verifier(),
        preserved_record=preserved,
        reconstructed_state=reconstructed,
    )
    residue = receipt["residue_verification"]
    assert receipt["final_verification"]["passed"] is True
    assert receipt["status"] == expected_status
    assert receipt["converged"] is (change == "preserved")
    assert receipt["runnable"] is (change == "preserved")
    assert residue["verified"] is (change == "preserved")
    assert residue["reason"] == {"preserved": "AUDITABLE_RESIDUE_VERIFIED", "omitted": "RECORDED_CONTRADICTION_OMITTED", "rewritten": "RECORDED_CONTRADICTION_REWRITTEN"}[change]
    assert residue["continuity_claimed"] is False
    assert residue["execution_authority"] == "NONE"
    for result in (receipt, residue):
        assert result["accepted"] is False
        assert result["truth_claimed"] is False
        assert result["write_authority"] == "NONE"
        body = {key: value for key, value in result.items() if key != "receipt_hash"}
        assert result["receipt_hash"] == stable_hash(body)
import json
import subprocess
from holosim.core import HoloChain
from holosim.witnessed_history_recovery import sign_history_witness

def test_fabricated_residue_cannot_claim_provenance(tmp_path):
    original = {"contradictions": [{"id": "observed-failure", "observed": "failure"}]}
    fabricated = {"contradictions": [{"id": "invented-success", "observed": "success"}]}
    chain_path = tmp_path / "chain.jsonl"
    HoloChain(chain_path).append(original)
    private_key = tmp_path / "test_signer"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)], check=True, capture_output=True)
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("test-signer " + private_key.with_suffix(".pub").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
    witness = sign_history_witness(chain_path=chain_path, chain_id="test-chain", signer_identity="test-signer", private_key_path=private_key)
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")
    receipt = run_software_convergence_request(REQUEST, tmp_path, _decomposer, _comparator, _proposer, _capability_verifier, _project_verifier, residue_verifier=build_auditable_residue_verifier(), preserved_record=fabricated, reconstructed_state=fabricated, residue_source={"chain_path": chain_path, "witness_path": witness_path, "expected_chain_id": "test-chain", "allowed_signers_path": allowed, "entry_idx": 1})
    assert receipt["status"] == "RESIDUE_PROVENANCE_FAILED"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False


def test_witnessed_residue_can_converge(tmp_path):
    original = {"contradictions": [{"id": "observed-failure", "observed": "failure"}]}
    fabricated = {"contradictions": [{"id": "invented-success", "observed": "success"}]}
    chain_path = tmp_path / "chain.jsonl"
    HoloChain(chain_path).append(original)
    private_key = tmp_path / "test_signer"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)], check=True, capture_output=True)
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("test-signer " + private_key.with_suffix(".pub").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
    witness = sign_history_witness(chain_path=chain_path, chain_id="test-chain", signer_identity="test-signer", private_key_path=private_key)
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")
    receipt = run_software_convergence_request(REQUEST, tmp_path, _decomposer, _comparator, _proposer, _capability_verifier, _project_verifier, residue_verifier=build_auditable_residue_verifier(), preserved_record=original, reconstructed_state=original, residue_source={"chain_path": chain_path, "witness_path": witness_path, "expected_chain_id": "test-chain", "allowed_signers_path": allowed, "entry_idx": 1})
    assert receipt["status"] == "RESIDUE_PROVENANCE_FAILED"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False


def test_residue_provenance_rejects_missing_witness(tmp_path):
    original = {"contradictions": [{"id": "observed-failure", "observed": "failure"}]}
    fabricated = {"contradictions": [{"id": "invented-success", "observed": "success"}]}
    chain_path = tmp_path / "chain.jsonl"
    HoloChain(chain_path).append(original)
    private_key = tmp_path / "test_signer"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)], check=True, capture_output=True)
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("test-signer " + private_key.with_suffix(".pub").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
    witness = sign_history_witness(chain_path=chain_path, chain_id="test-chain", signer_identity="test-signer", private_key_path=private_key)
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")
    receipt = run_software_convergence_request(REQUEST, tmp_path, _decomposer, _comparator, _proposer, _capability_verifier, _project_verifier, residue_verifier=build_auditable_residue_verifier(), preserved_record=original, reconstructed_state=original, residue_source={"chain_path": chain_path, "witness_path": tmp_path / "missing-witness.json", "expected_chain_id": "test-chain", "allowed_signers_path": allowed, "entry_idx": 1})
    assert receipt["status"] == "RESIDUE_PROVENANCE_FAILED"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False


def test_residue_provenance_rejects_wrong_index(tmp_path):
    original = {"contradictions": [{"id": "observed-failure", "observed": "failure"}]}
    fabricated = {"contradictions": [{"id": "invented-success", "observed": "success"}]}
    chain_path = tmp_path / "chain.jsonl"
    HoloChain(chain_path).append(original)
    private_key = tmp_path / "test_signer"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)], check=True, capture_output=True)
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("test-signer " + private_key.with_suffix(".pub").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
    witness = sign_history_witness(chain_path=chain_path, chain_id="test-chain", signer_identity="test-signer", private_key_path=private_key)
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")
    receipt = run_software_convergence_request(REQUEST, tmp_path, _decomposer, _comparator, _proposer, _capability_verifier, _project_verifier, residue_verifier=build_auditable_residue_verifier(), preserved_record=original, reconstructed_state=original, residue_source={"chain_path": chain_path, "witness_path": witness_path, "expected_chain_id": "test-chain", "allowed_signers_path": allowed, "entry_idx": 2})
    assert receipt["status"] == "RESIDUE_PROVENANCE_FAILED"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False


def test_residue_provenance_rejects_wrong_chain_id(tmp_path):
    original = {"contradictions": [{"id": "observed-failure", "observed": "failure"}]}
    fabricated = {"contradictions": [{"id": "invented-success", "observed": "success"}]}
    chain_path = tmp_path / "chain.jsonl"
    HoloChain(chain_path).append(original)
    private_key = tmp_path / "test_signer"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)], check=True, capture_output=True)
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("test-signer " + private_key.with_suffix(".pub").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
    witness = sign_history_witness(chain_path=chain_path, chain_id="test-chain", signer_identity="test-signer", private_key_path=private_key)
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")
    receipt = run_software_convergence_request(REQUEST, tmp_path, _decomposer, _comparator, _proposer, _capability_verifier, _project_verifier, residue_verifier=build_auditable_residue_verifier(), preserved_record=original, reconstructed_state=original, residue_source={"chain_path": chain_path, "witness_path": witness_path, "expected_chain_id": "wrong-chain", "allowed_signers_path": allowed, "entry_idx": 1})
    assert receipt["status"] == "RESIDUE_PROVENANCE_FAILED"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False
import pytest

@pytest.mark.parametrize("invalid_source", [
    {},
    {"entry_idx": True},
    {"entry_idx": 1, "unexpected": "value"},
])
def test_malformed_residue_source_rejected(tmp_path, invalid_source):
    from holosim.software_convergence_entrypoint import run_software_convergence_request
    from holosim.auditable_residue_verifier import build_auditable_residue_verifier
    record = {"contradictions": [{"id": "fabricated", "observed": "success"}]}
    receipt = run_software_convergence_request(REQUEST, tmp_path, _decomposer, _comparator, _proposer, _capability_verifier, _project_verifier, residue_verifier=build_auditable_residue_verifier(), preserved_record=record, reconstructed_state=record, residue_source=invalid_source)
    assert receipt["status"] == "RESIDUE_PROVENANCE_FAILED"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False
    assert receipt["residue_provenance"] is None
    assert receipt["residue_verification"] is None
def test_forged_residue_verifier_cannot_promote_convergence(tmp_path):
    preserved = {"contradictions": [{"id": "failure", "observed": "failed"}]}
    reconstructed = {"contradictions": []}
    def forged_verifier(**kwargs):
        return {"verified": True, "reason": "FABRICATED_SUCCESS"}
    receipt = run_software_convergence_request(REQUEST, tmp_path, _decomposer, _comparator, _proposer, _capability_verifier, _project_verifier, residue_verifier=forged_verifier, preserved_record=preserved, reconstructed_state=reconstructed)
    assert receipt["status"] == "RESIDUE_VERIFICATION_FAILED"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False


def test_required_provenance_rejects_fabricated_matching_residue(tmp_path):
    fabricated = {"contradictions": [{"id": "invented-success", "observed": "success"}]}
    receipt = run_software_convergence_request(
        REQUEST, tmp_path, _decomposer, _comparator, _proposer,
        _capability_verifier, _project_verifier,
        residue_verifier=build_auditable_residue_verifier(),
        preserved_record=fabricated,
        reconstructed_state=fabricated,
        require_residue_provenance=True,
    )
    assert receipt["status"] == "RESIDUE_PROVENANCE_FAILED"
    assert receipt["converged"] is False
    assert receipt["runnable"] is False
    assert receipt["version"] == 1
    assert "residue_provenance" not in receipt


@pytest.mark.parametrize(("digest_case", "expected_status"), [
    ("missing", "RESIDUE_PROVENANCE_FAILED"),
    ("mismatch", "RESIDUE_PROVENANCE_FAILED"),
    ("invalid", "RESIDUE_PROVENANCE_FAILED"),
    ("matching", "RESIDUE_PROVENANCE_UNAUTHENTICATED"),
])
@pytest.mark.parametrize("fabricated", [False, True])
def test_required_provenance_policy_pin(tmp_path, digest_case, expected_status, fabricated):
    import hashlib
    import shutil
    from pathlib import Path
    from holosim.core import HoloChain
    from holosim.witnessed_history_recovery import sign_history_witness

    if shutil.which("ssh-keygen") is None:
        pytest.skip("OpenSSH required")

    record = {"contradictions": [{"id": "invented-success" if fabricated else "observed-failure", "observed": "success" if fabricated else "failure"}]}
    chain = tmp_path / "chain.jsonl"
    HoloChain(chain).append(record)
    key = tmp_path / "signer"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True, capture_output=True)
    policy = tmp_path / "allowed_signers"
    policy.write_text("test-signer " + Path(str(key) + ".pub").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
    witness = sign_history_witness(chain_path=chain, chain_id="test-chain", signer_identity="test-signer", private_key_path=key)
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")
    correct_digest = hashlib.sha256(policy.read_bytes()).hexdigest()
    digest = {"missing": None, "mismatch": "0" * 64, "invalid": "not-a-digest", "matching": correct_digest}[digest_case]
    receipt = run_software_convergence_request(
        REQUEST, tmp_path, _decomposer, _comparator, _proposer,
        _capability_verifier, _project_verifier,
        residue_verifier=build_auditable_residue_verifier(),
        preserved_record=record,
        reconstructed_state=record,
        residue_source={"chain_path": chain, "witness_path": witness_path, "expected_chain_id": "test-chain", "allowed_signers_path": policy, "entry_idx": 1},
        require_residue_provenance=True,
        expected_policy_sha256=digest,
    )
    assert receipt["status"] == expected_status
    assert receipt["converged"] is False
    assert receipt["runnable"] is False
    if digest_case == "matching":
        assert receipt["residue_provenance"]["status"] == "VERIFIED_SOURCE_MEMBERSHIP"
        assert receipt["residue_provenance"]["verified"] is True
        assert receipt["residue_policy_binding"]["policy_digest_matched"] is True
        assert receipt["residue_policy_binding"]["provenance_authenticated"] is False
        assert receipt["terminal_reason"] == "INDEPENDENT_PROVENANCE_AUTHENTICATION_REQUIRED"
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["receipt_hash"] == stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
    binding = receipt["residue_policy_binding"]
    expected_binding_status = {
        "missing": "NOT_ATTEMPTED",
        "mismatch": "REJECTED_POLICY",
        "invalid": "REJECTED_POLICY",
        "matching": "MATCHED",
    }[digest_case]
    assert receipt["version"] == 2
    assert binding["status"] == expected_binding_status
    assert binding["expected_policy_sha256"] == digest
    assert binding["policy_digest_matched"] is (digest_case == "matching")
    assert binding["policy_custody_verified"] is False
    assert binding["provenance_authenticated"] is False
    tampered = deepcopy(receipt)
    tampered["residue_policy_binding"]["policy_digest_matched"] = not binding["policy_digest_matched"]
    assert tampered["receipt_hash"] != stable_hash({k: v for k, v in tampered.items() if k != "receipt_hash"})



def test_convergence_uses_captured_policy_after_replacement(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path
    import holosim.software_convergence_entrypoint as module

    original = b"original signer policy\n"
    replacement = b"attacker signer policy\n"
    policy = tmp_path / "allowed_signers"
    policy.write_bytes(original)
    observed = {}

    def capture_then_replace(**kwargs):
        captured = real_capture(**kwargs)
        policy.write_bytes(replacement)
        return captured

    def observe_membership(**kwargs):
        observed["policy_bytes"] = Path(kwargs["allowed_signers_path"]).read_bytes()
        body = {"type": "witnessed_source_membership", "version": 1, "status": "VERIFIED_SOURCE_MEMBERSHIP", "verified": True, "history_receipt_hash": None, "accepted": False, "truth_claimed": False, "write_authority": "NONE", "execution_authority": "NONE"}
        return {**body, "receipt_hash": stable_hash(body)}

    real_capture = module.capture_pinned_signer_policy
    monkeypatch.setattr(module, "capture_pinned_signer_policy", capture_then_replace)
    monkeypatch.setattr(module, "verify_witnessed_source_membership", observe_membership)

    record = {"contradictions": [{"id": "observed-failure", "observed": "failure"}]}
    receipt = module.run_software_convergence_request(
        REQUEST, tmp_path, _decomposer, _comparator, _proposer,
        _capability_verifier, _project_verifier,
        residue_verifier=build_auditable_residue_verifier(),
        preserved_record=record,
        reconstructed_state=record,
        residue_source={"chain_path": tmp_path / "chain", "witness_path": tmp_path / "witness", "expected_chain_id": "fixture", "allowed_signers_path": policy, "entry_idx": 1},
        require_residue_provenance=True,
        expected_policy_sha256=hashlib.sha256(original).hexdigest(),
    )
    assert observed["policy_bytes"] == original
    assert policy.read_bytes() == replacement
    assert receipt["status"] == "RESIDUE_PROVENANCE_UNAUTHENTICATED"
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
