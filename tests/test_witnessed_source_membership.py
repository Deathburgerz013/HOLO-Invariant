from holosim.witnessed_source_membership import verify_witnessed_source_membership
def test_missing_witness_rejects_membership(tmp_path):
    result = verify_witnessed_source_membership(
        chain_path=tmp_path / "chain.jsonl",
        witness_path=tmp_path / "missing-witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed_signers",
        source_bindings=[{"entry_idx": 1, "source_item": {"id": "invented"}}],
    )
    assert result["status"] == "REJECTED_HISTORY"
    assert result["verified"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
import json
import subprocess
from holosim.core import HoloChain
from holosim.witnessed_history_recovery import sign_history_witness
from holosim.witnessed_source_membership import verify_witnessed_source_membership

def test_signed_history_rejects_unwitnessed_source(tmp_path):
    registration = dict(id="registration-red", requires=[], observation="red", registered=True)
    contradiction = dict(id="contradiction-unwitnessed", requires=[], observation="invented")
    chain_path = tmp_path / "chain.jsonl"
    HoloChain(chain_path).append(registration)
    private_key = tmp_path / "test_signer"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)], check=True, capture_output=True)
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("test-signer " + private_key.with_suffix(".pub").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
    witness = sign_history_witness(chain_path=chain_path, chain_id="test-chain", signer_identity="test-signer", private_key_path=private_key)
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")
    common = dict(chain_path=chain_path, witness_path=witness_path, expected_chain_id="test-chain", allowed_signers_path=allowed)
    from unittest.mock import patch
    original_load = HoloChain.load_and_verify
    def guarded_load(self):
        assert type(chain_path)(self.file_path).resolve() != chain_path.resolve(), "membership reopened original chain"
        return original_load(self)
    with patch.object(HoloChain, "load_and_verify", guarded_load):
        valid = verify_witnessed_source_membership(**common, source_bindings=[dict(entry_idx=1, source_item=registration)])
    assert valid["status"] == "VERIFIED_SOURCE_MEMBERSHIP"
    assert valid["verified"] is True
    fabricated = verify_witnessed_source_membership(**common, source_bindings=[dict(entry_idx=1, source_item=registration), dict(entry_idx=2, source_item=contradiction)])
    assert fabricated["status"] == "REJECTED_SOURCE_MEMBERSHIP"
    assert fabricated["verified"] is False
    for result in (valid, fabricated):
        assert result["accepted"] is False
        assert result["truth_claimed"] is False
        assert result["write_authority"] == "NONE"
        assert result["execution_authority"] == "NONE"
    invalid_cases = [
        [dict(entry_idx=1, source_item=registration), dict(entry_idx=1, source_item=registration)],
        [dict(entry_idx=1, source_item=dict(registration, observation="altered"))],
        [dict(entry_idx=True, source_item=registration)],
        [],
    ]
    for bindings in invalid_cases:
        rejected = verify_witnessed_source_membership(**common, source_bindings=bindings)
        assert rejected["status"] == "REJECTED_SOURCE_MEMBERSHIP"
        assert rejected["verified"] is False
        assert rejected["accepted"] is False
        assert rejected["write_authority"] == "NONE"
        assert rejected["execution_authority"] == "NONE"
    import holosim.witnessed_source_membership as membership
    from unittest.mock import patch
    from holosim.witnessed_history_recovery import recover_witnessed_history
    original_recovery = membership._recover_witnessed_history_with_entries
    def capture_then_mutate(**kwargs):
        history, entries = original_recovery(**kwargs)
        HoloChain(chain_path).append(dict(id="post-capture-entry"))
        return history, entries
    with patch.object(membership, "_recover_witnessed_history_with_entries", capture_then_mutate):
        after_capture = verify_witnessed_source_membership(**common, source_bindings=[dict(entry_idx=1, source_item=registration)])
    assert after_capture["status"] == "VERIFIED_SOURCE_MEMBERSHIP"
    assert after_capture["verified"] is True
    assert after_capture["accepted"] is False
    assert after_capture["write_authority"] == "NONE"
    current_history = recover_witnessed_history(**common)
    assert current_history["status"] == "REJECTED_COUNT"
    HoloChain(chain_path).append(dict(id="post-witness-entry"))
    changed = verify_witnessed_source_membership(**common, source_bindings=[dict(entry_idx=1, source_item=registration)])
    assert changed["status"] == "REJECTED_HISTORY"
    assert changed["verified"] is False
    assert changed["accepted"] is False
    assert changed["truth_claimed"] is False
    assert changed["write_authority"] == "NONE"
    assert changed["execution_authority"] == "NONE"
