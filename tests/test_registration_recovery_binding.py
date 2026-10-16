from holosim.core import HoloChain
from holosim.registration_recovery_binding import evaluate_witnessed_registration_recovery


def test_unwitnessed_registration_cannot_be_recovered_as_verified(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    chain = HoloChain(chain_path)

    registration = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }
    chain.append(registration)

    receipt = evaluate_witnessed_registration_recovery(
        chain_path=chain_path,
        witness_path=tmp_path / "missing-witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    assert receipt["status"] == "REJECTED_HISTORY"
    assert receipt["recognized"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

def test_chain_change_after_witness_check_cannot_verify_registration(tmp_path, monkeypatch):
    from holosim import registration_recovery_binding as module

    chain_path = tmp_path / "chain.jsonl"
    chain = HoloChain(chain_path)

    original = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }
    chain.append(original)

    def simulated_witness_check(**kwargs):
        chain.append({"id": "injected", "registered": True})
        return {
            "status": "MATCHED",
            "receipt_hash": "simulated-history-receipt",
        }

    monkeypatch.setattr(
        module,
        "recover_witnessed_history",
        simulated_witness_check,
    )

    receipt = module.evaluate_witnessed_registration_recovery(
        chain_path=chain_path,
        witness_path=tmp_path / "witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item=original,
        observation="red",
    )

    assert receipt["status"] == "REJECTED_HISTORY"
    assert receipt["recognized"] is False
def test_valid_signed_history_recovers_exact_registration(tmp_path):
    import json
    import subprocess

    from holosim.witnessed_history_recovery import sign_history_witness

    chain_path = tmp_path / "chain.jsonl"
    chain = HoloChain(chain_path)

    registration = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }
    chain.append(registration)

    private_key = tmp_path / "test_signer"
    subprocess.run(
        [
            "ssh-keygen", "-q", "-t", "ed25519",
            "-N", "", "-f", str(private_key),
        ],
        check=True,
        capture_output=True,
    )

    allowed_signers = tmp_path / "allowed_signers"
    public_key = private_key.with_suffix(".pub").read_text(encoding="utf-8").strip()
    allowed_signers.write_text(
        f"test-signer {public_key}\n",
        encoding="utf-8",
    )

    witness = sign_history_witness(
        chain_path=chain_path,
        chain_id="test-chain",
        signer_identity="test-signer",
        private_key_path=private_key,
    )
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    receipt = evaluate_witnessed_registration_recovery(
        chain_path=chain_path,
        witness_path=witness_path,
        expected_chain_id="test-chain",
        allowed_signers_path=allowed_signers,
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    assert receipt["status"] == "VERIFIED_REGISTRATION"
    assert receipt["recognized"] is True
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

def test_registration_injected_after_witness_is_rejected(tmp_path):
    import json
    import subprocess

    from holosim.witnessed_history_recovery import sign_history_witness

    chain_path = tmp_path / "chain.jsonl"
    chain = HoloChain(chain_path)
    chain.append({"id": "original", "observation": "blue", "registered": True})

    private_key = tmp_path / "test_signer"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        check=True,
        capture_output=True,
    )

    allowed_signers = tmp_path / "allowed_signers"
    public_key = private_key.with_suffix(".pub").read_text(encoding="utf-8").strip()
    allowed_signers.write_text(f"test-signer {public_key}\n", encoding="utf-8")

    witness = sign_history_witness(
        chain_path=chain_path,
        chain_id="test-chain",
        signer_identity="test-signer",
        private_key_path=private_key,
    )
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    injected = {"id": "injected", "observation": "red", "registered": True}
    chain.append(injected)

    assert len(chain.load_and_verify()) == 2

    receipt = evaluate_witnessed_registration_recovery(
        chain_path=chain_path,
        witness_path=witness_path,
        expected_chain_id="test-chain",
        allowed_signers_path=allowed_signers,
        registration_entry_idx=2,
        registration_item=injected,
        observation="red",
    )

    assert receipt["status"] == "REJECTED_HISTORY"
    assert receipt["recognized"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

def test_recovery_receipt_detects_status_tampering(tmp_path):
    from holosim.registration_recovery_binding import (
        verify_witnessed_registration_recovery_receipt,
    )

    chain = HoloChain(tmp_path / "chain.jsonl")
    chain.append({"id": "registration-red", "registered": True})

    receipt = evaluate_witnessed_registration_recovery(
        chain_path=tmp_path / "chain.jsonl",
        witness_path=tmp_path / "missing-witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item={"id": "registration-red", "registered": True},
        observation="red",
    )

    assert verify_witnessed_registration_recovery_receipt(receipt) is True

    altered = dict(receipt)
    altered["status"] = "VERIFIED_REGISTRATION"
    altered["recognized"] = True

    assert verify_witnessed_registration_recovery_receipt(altered) is False

def test_invalid_registration_index_produces_verifiable_rejection(tmp_path, monkeypatch):
    from holosim import registration_recovery_binding as module

    chain_path = tmp_path / "chain.jsonl"
    chain = HoloChain(chain_path)
    entry = chain.append({"id": "registration-red", "registered": True})

    monkeypatch.setattr(
        module,
        "recover_witnessed_history",
        lambda **kwargs: {
            "status": "MATCHED",
            "observed": {
                "entry_count": 1,
                "head_hash": entry["hash"],
            },
            "receipt_hash": "simulated-history-receipt",
        },
    )

    receipt = module.evaluate_witnessed_registration_recovery(
        chain_path=chain_path,
        witness_path=tmp_path / "witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=0,
        registration_item={"id": "registration-red", "registered": True},
        observation="red",
    )

    assert receipt["status"] == "REJECTED_REGISTRATION"
    assert receipt["recognized"] is False
    assert module.verify_witnessed_registration_recovery_receipt(receipt) is True

def test_malformed_registration_indices_fail_closed(tmp_path, monkeypatch):
    from holosim import registration_recovery_binding as module

    chain_path = tmp_path / "chain.jsonl"
    chain = HoloChain(chain_path)
    entry = chain.append({
        "id": "registration-red",
        "observation": "red",
        "registered": True,
    })

    monkeypatch.setattr(
        module,
        "recover_witnessed_history",
        lambda **kwargs: {
            "status": "MATCHED",
            "observed": {
                "entry_count": 1,
                "head_hash": entry["hash"],
            },
            "receipt_hash": "simulated-history-receipt",
        },
    )

    for invalid_index in (True, False, "1", None, 1.0, -1):
        receipt = module.evaluate_witnessed_registration_recovery(
            chain_path=chain_path,
            witness_path=tmp_path / "witness.json",
            expected_chain_id="test-chain",
            allowed_signers_path=tmp_path / "allowed-signers",
            registration_entry_idx=invalid_index,
            registration_item={
                "id": "registration-red",
                "observation": "red",
                "registered": True,
            },
            observation="red",
        )

        assert receipt["status"] == "REJECTED_REGISTRATION"
        assert receipt["recognized"] is False
        assert receipt["accepted"] is False
        assert receipt["write_authority"] == "NONE"
        assert receipt["execution_authority"] == "NONE"
        assert module.verify_witnessed_registration_recovery_receipt(receipt)

def test_forged_success_with_invalid_index_is_rejected():
    from holosim.canonical import stable_hash
    from holosim.registration_recovery_binding import (
        verify_witnessed_registration_recovery_receipt,
    )

    for invalid_index in (0, -1, True, False, "1", None, 1.0):
        body = {
            "type": "witnessed_registration_recovery",
            "version": 1,
            "status": "VERIFIED_REGISTRATION",
            "recognized": True,
            "registration_entry_idx": invalid_index,
            "history_receipt_hash": "simulated-history-receipt",
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }

        forged_receipt = {
            **body,
            "receipt_hash": stable_hash(body),
        }

        assert verify_witnessed_registration_recovery_receipt(
            forged_receipt
        ) is False

def test_tampered_signed_witness_cannot_verify_registration(tmp_path):
    import json
    import subprocess

    from holosim.witnessed_history_recovery import sign_history_witness

    chain_path = tmp_path / "chain.jsonl"
    chain = HoloChain(chain_path)

    registration = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }
    chain.append(registration)

    private_key = tmp_path / "test_signer"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        check=True,
        capture_output=True,
    )

    allowed_signers = tmp_path / "allowed_signers"
    public_key = private_key.with_suffix(".pub").read_text(
        encoding="utf-8"
    ).strip()
    allowed_signers.write_text(
        f"test-signer {public_key}\n",
        encoding="utf-8",
    )

    witness = sign_history_witness(
        chain_path=chain_path,
        chain_id="test-chain",
        signer_identity="test-signer",
        private_key_path=private_key,
    )

    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    valid_receipt = evaluate_witnessed_registration_recovery(
        chain_path=chain_path,
        witness_path=witness_path,
        expected_chain_id="test-chain",
        allowed_signers_path=allowed_signers,
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )
    assert valid_receipt["status"] == "VERIFIED_REGISTRATION"

    witness_path.write_text(
        json.dumps({**witness, "chain_id": "tampered-chain"}),
        encoding="utf-8",
    )

    rejected = evaluate_witnessed_registration_recovery(
        chain_path=chain_path,
        witness_path=witness_path,
        expected_chain_id="test-chain",
        allowed_signers_path=allowed_signers,
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    assert rejected["status"] == "REJECTED_HISTORY"
    assert rejected["recognized"] is False
    assert rejected["accepted"] is False
    assert rejected["write_authority"] == "NONE"
    assert rejected["execution_authority"] == "NONE"

def test_signed_history_rejects_registration_and_observation_mismatch(
    tmp_path, monkeypatch
):
    import json
    import subprocess

    from holosim.witnessed_history_recovery import sign_history_witness

    chain_path = tmp_path / "chain.jsonl"
    chain = HoloChain(chain_path)

    registration = {
        "id": "registration-red",
        "observation": "red",
        "registered": True,
    }
    chain.append(registration)

    private_key = tmp_path / "test_signer"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        check=True,
        capture_output=True,
    )

    allowed_signers = tmp_path / "allowed_signers"
    public_key = private_key.with_suffix(".pub").read_text(
        encoding="utf-8"
    ).strip()
    allowed_signers.write_text(
        f"test-signer {public_key}\n",
        encoding="utf-8",
    )

    witness = sign_history_witness(
        chain_path=chain_path,
        chain_id="test-chain",
        signer_identity="test-signer",
        private_key_path=private_key,
    )
    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    cases = (
        ({**registration, "id": "injected"}, "red"),
        (registration, "blue"),
        ({**registration, "registered": False}, "red"),
    )

    for supplied_item, supplied_observation in cases:
        receipt = evaluate_witnessed_registration_recovery(
            chain_path=chain_path,
            witness_path=witness_path,
            expected_chain_id="test-chain",
            allowed_signers_path=allowed_signers,
            registration_entry_idx=1,
            registration_item=supplied_item,
            observation=supplied_observation,
        )

        assert receipt["status"] == "REJECTED_REGISTRATION"
        assert receipt["recognized"] is False
        assert receipt["accepted"] is False
        assert receipt["write_authority"] == "NONE"
        assert receipt["execution_authority"] == "NONE"

def test_chain_read_failure_after_witness_check_rejects_history(
    tmp_path, monkeypatch
):
    from holosim import registration_recovery_binding as module

    chain_path = tmp_path / "chain.jsonl"
    registration = {
        "id": "registration-red",
        "observation": "red",
        "registered": True,
    }
    HoloChain(chain_path).append(registration)

    monkeypatch.setattr(
        module,
        "recover_witnessed_history",
        lambda **kwargs: {
            "status": "MATCHED",
            "observed": {
                "entry_count": 1,
                "head_hash": "0" * 64,
            },
            "receipt_hash": "simulated-history-receipt",
        },
    )

    def failed_chain_read(self):
        raise ValueError("chain verification failed")

    monkeypatch.setattr(
        module.HoloChain,
        "load_and_verify",
        failed_chain_read,
    )

    receipt = module.evaluate_witnessed_registration_recovery(
        chain_path=chain_path,
        witness_path=tmp_path / "witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    assert receipt["status"] == "REJECTED_HISTORY"
    assert receipt["recognized"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

def test_valid_reconstruction_without_witness_cannot_claim_registration(tmp_path):
    from holosim.reconstructor import (
        build_reconstructed_state,
        validate_reconstructed_state,
    )

    registration = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }
    source_items = [registration]

    state = build_reconstructed_state(
        "test-reference",
        ["registration-red"],
        source_items,
    )

    assert validate_reconstructed_state(state, source_items) is True
    assert registration in state["carried_items"]

    from holosim.registration_recovery_binding import (
        evaluate_witnessed_reconstructed_registration,
    )

    receipt = evaluate_witnessed_reconstructed_registration(
        reconstructed_state=state,
        source_items=source_items,
        chain_path=tmp_path / "missing-chain.jsonl",
        witness_path=tmp_path / "missing-witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    assert receipt["recognized"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

def test_valid_signed_history_and_reconstruction_recognize_registration(tmp_path):
    import json
    import subprocess

    from holosim.reconstructor import build_reconstructed_state
    from holosim.registration_recovery_binding import (
        evaluate_witnessed_reconstructed_registration,
    )
    from holosim.witnessed_history_recovery import sign_history_witness

    registration = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }

    chain_path = tmp_path / "chain.jsonl"
    HoloChain(chain_path).append(registration)

    private_key = tmp_path / "test_signer"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        check=True,
        capture_output=True,
    )

    allowed_signers = tmp_path / "allowed_signers"
    public_key = private_key.with_suffix(".pub").read_text(
        encoding="utf-8"
    ).strip()
    allowed_signers.write_text(
        f"test-signer {public_key}\n",
        encoding="utf-8",
    )

    witness = sign_history_witness(
        chain_path=chain_path,
        chain_id="test-chain",
        signer_identity="test-signer",
        private_key_path=private_key,
    )

    witness_path = tmp_path / "witness.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    state = build_reconstructed_state(
        "test-reference",
        ["registration-red"],
        [registration],
    )

    result = evaluate_witnessed_reconstructed_registration(
        reconstructed_state=state,
        source_items=[registration],
        chain_path=chain_path,
        witness_path=witness_path,
        expected_chain_id="test-chain",
        allowed_signers_path=allowed_signers,
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    assert result["reconstruction_valid"] is True
    assert result["history_status"] == "VERIFIED_REGISTRATION"
    assert result["status"] == "VERIFIED_REGISTRATION"
    assert result["recognized"] is True
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"

def test_tampered_reconstruction_cannot_borrow_witnessed_registration(
    tmp_path, monkeypatch
):
    from holosim import registration_recovery_binding as module
    from holosim.reconstructor import build_reconstructed_state

    registration = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }

    state = build_reconstructed_state(
        "test-reference",
        ["registration-red"],
        [registration],
    )

    tampered = dict(state)
    tampered["carried_items"] = [
        {**registration, "observation": "blue"}
    ]

    def witnessed_registration(**kwargs):
        return {
            "status": "VERIFIED_REGISTRATION",
            "recognized": True,
            "receipt_hash": "simulated-history-receipt",
        }

    monkeypatch.setattr(
        module,
        "evaluate_witnessed_registration_recovery",
        witnessed_registration,
    )

    result = module.evaluate_witnessed_reconstructed_registration(
        reconstructed_state=tampered,
        source_items=[registration],
        chain_path=tmp_path / "chain.jsonl",
        witness_path=tmp_path / "witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    assert result["reconstruction_valid"] is False
    assert result["recognized"] is False
    assert result["status"] == "REJECTED_REGISTRATION"
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"

def test_valid_reconstruction_missing_registration_has_verifiable_rejection(
    tmp_path, monkeypatch
):
    from holosim import registration_recovery_binding as module
    from holosim.reconstructor import build_reconstructed_state

    registration = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }
    unrelated = {
        "id": "unrelated",
        "requires": [],
        "observation": "blue",
        "registered": True,
    }

    state = build_reconstructed_state(
        "test-reference",
        ["unrelated"],
        [registration, unrelated],
    )

    def witnessed_registration(**kwargs):
        return {
            "status": "VERIFIED_REGISTRATION",
            "recognized": True,
            "receipt_hash": "simulated-history-receipt",
        }

    monkeypatch.setattr(
        module,
        "evaluate_witnessed_registration_recovery",
        witnessed_registration,
    )

    receipt = module.evaluate_witnessed_reconstructed_registration(
        reconstructed_state=state,
        source_items=[registration, unrelated],
        chain_path=tmp_path / "chain.jsonl",
        witness_path=tmp_path / "witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    assert receipt["reconstruction_valid"] is True
    assert receipt["history_status"] == "VERIFIED_REGISTRATION"
    assert receipt["recognized"] is False
    assert receipt["status"] == "REJECTED_REGISTRATION"
    assert module.verify_witnessed_reconstructed_registration_receipt(
        receipt
    ) is True

def test_combined_receipt_integrity_and_authority_tampering(
    tmp_path, monkeypatch
):
    from holosim import registration_recovery_binding as module
    from holosim.canonical import stable_hash
    from holosim.reconstructor import build_reconstructed_state

    registration = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }

    state = build_reconstructed_state(
        "test-reference",
        ["registration-red"],
        [registration],
    )

    def witnessed_registration(**kwargs):
        return {
            "status": "VERIFIED_REGISTRATION",
            "recognized": True,
            "receipt_hash": "simulated-history-receipt",
        }

    monkeypatch.setattr(
        module,
        "evaluate_witnessed_registration_recovery",
        witnessed_registration,
    )

    receipt = module.evaluate_witnessed_reconstructed_registration(
        reconstructed_state=state,
        source_items=[registration],
        chain_path=tmp_path / "chain.jsonl",
        witness_path=tmp_path / "witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    verify = module.verify_witnessed_reconstructed_registration_receipt

    assert verify(receipt) is True

    for field, value in [
        ("recognized", False),
        ("registration_carried", False),
        ("reconstruction_valid", False),
        ("history_status", "REJECTED_HISTORY"),
        ("status", "REJECTED_REGISTRATION"),
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
    ]:
        tampered = dict(receipt)
        tampered[field] = value
        assert verify(tampered) is False, field

        body = {
            key: value
            for key, value in tampered.items()
            if key != "receipt_hash"
        }
        tampered["receipt_hash"] = stable_hash(body)

        if field in {
            "accepted",
            "truth_claimed",
            "write_authority",
            "execution_authority",
            "recognized",
            "registration_carried",
            "reconstruction_valid",
            "history_status",
            "status",
        }:
            assert verify(tampered) is False, field

def test_decode_failure_after_verified_snapshot_returns_rejection(
    tmp_path, monkeypatch
):
    from holosim import registration_recovery_binding as module

    monkeypatch.setattr(
        module,
        "recover_witnessed_history",
        lambda **kwargs: {
            "status": "MATCHED",
            "observed": {
                "entry_count": 1,
                "head_hash": "a" * 64,
            },
            "receipt_hash": "simulated-history-receipt",
        },
    )

    monkeypatch.setattr(
        module.HoloChain,
        "load_and_verify",
        lambda self: [{"hash": "a" * 64}],
    )

    def reject_decode(entries):
        raise ValueError("malformed entry content")

    monkeypatch.setattr(
        module.HoloChain,
        "_decode_entries",
        reject_decode,
    )

    receipt = module.evaluate_witnessed_registration_recovery(
        chain_path=tmp_path / "chain.jsonl",
        witness_path=tmp_path / "witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item={
            "id": "registration-red",
            "registered": True,
            "observation": "red",
        },
        observation="red",
    )

    assert receipt["status"] == "REJECTED_REGISTRATION"
    assert receipt["recognized"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert module.verify_witnessed_registration_recovery_receipt(
        receipt
    ) is True

def test_unexpected_reconstruction_validation_error_returns_rejection(
    tmp_path, monkeypatch
):
    from holosim import registration_recovery_binding as module
    from holosim import reconstructor

    def broken_validation(state, items):
        raise TypeError("unexpected validation failure")

    monkeypatch.setattr(
        reconstructor,
        "validate_reconstructed_state",
        broken_validation,
    )

    monkeypatch.setattr(
        module,
        "evaluate_witnessed_registration_recovery",
        lambda **kwargs: {
            "status": "VERIFIED_REGISTRATION",
            "recognized": True,
            "receipt_hash": "simulated-history-receipt",
        },
    )

    registration = {
        "id": "registration-red",
        "requires": [],
        "observation": "red",
        "registered": True,
    }

    receipt = module.evaluate_witnessed_reconstructed_registration(
        reconstructed_state={"carried_items": [registration]},
        source_items=[registration],
        chain_path=tmp_path / "chain.jsonl",
        witness_path=tmp_path / "witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item=registration,
        observation="red",
    )

    assert receipt["reconstruction_valid"] is False
    assert receipt["recognized"] is False
    assert receipt["status"] == "REJECTED_REGISTRATION"
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert module.verify_witnessed_reconstructed_registration_receipt(
        receipt
    ) is True

def test_history_recovery_exception_returns_structured_rejection(
    tmp_path, monkeypatch
):
    from holosim import registration_recovery_binding as module

    def broken_history(**kwargs):
        raise OSError("history verification unavailable")

    monkeypatch.setattr(
        module,
        "recover_witnessed_history",
        broken_history,
    )

    receipt = module.evaluate_witnessed_registration_recovery(
        chain_path=tmp_path / "chain.jsonl",
        witness_path=tmp_path / "witness.json",
        expected_chain_id="test-chain",
        allowed_signers_path=tmp_path / "allowed-signers",
        registration_entry_idx=1,
        registration_item={
            "id": "registration-red",
            "registered": True,
            "observation": "red",
        },
        observation="red",
    )

    assert receipt["status"] == "REJECTED_HISTORY"
    assert receipt["recognized"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert module.verify_witnessed_registration_recovery_receipt(
        receipt
    ) is True
