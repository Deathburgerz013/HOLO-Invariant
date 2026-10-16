"""Read-only registration recovery against independently witnessed HoloChain history."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from holosim.canonical import stable_hash
from holosim.core import HoloChain
from holosim.witnessed_history_recovery import recover_witnessed_history


def evaluate_witnessed_registration_recovery(
    *,
    chain_path: str | Path,
    witness_path: str | Path,
    expected_chain_id: str,
    allowed_signers_path: str | Path,
    registration_entry_idx: int,
    registration_item: Mapping[str, Any],
    observation: Any,
) -> dict[str, Any]:
    """Recognize an exact registration only when independently witnessed history matches."""
    try:
        history = recover_witnessed_history(
            chain_path=chain_path,
            witness_path=witness_path,
            expected_chain_id=expected_chain_id,
            allowed_signers_path=allowed_signers_path,
        )
    except OSError:
        history = {
            "status": "REJECTED_HISTORY",
            "receipt_hash": stable_hash({
                "type": "history_recovery_unavailable",
                "version": 1,
                "status": "REJECTED_HISTORY",
            }),
        }

    status = "REJECTED_HISTORY"
    recognized = False

    if history["status"] == "MATCHED":
        if type(registration_entry_idx) is not int or registration_entry_idx < 1:
            status = "REJECTED_REGISTRATION"
        else:
            chain = HoloChain(chain_path)
            try:
                entries = chain.load_and_verify()
            except (ValueError, OSError):
                entries = None

            observed = history.get("observed")
            snapshot_matches = (
                entries is not None
                and
                type(observed) is dict
                and type(observed.get("entry_count")) is int
                and type(observed.get("head_hash")) is str
                and observed["entry_count"] == len(entries)
                and observed["head_hash"]
                == (entries[-1]["hash"] if entries else "0" * 64)
            )

            if not snapshot_matches:
                status = "REJECTED_HISTORY"
            elif registration_entry_idx > len(entries):
                status = "REJECTED_REGISTRATION"
            else:
                try:
                    decoded = HoloChain._decode_entries(
                        [entries[registration_entry_idx - 1]]
                    )[0]
                except (ValueError, TypeError, KeyError, IndexError):
                    decoded = None

                if (
                    type(decoded) is dict
                    and type(registration_item) is dict
                    and decoded == registration_item
                    and decoded.get("registered") is True
                    and decoded.get("observation") == observation
                ):
                    status = "VERIFIED_REGISTRATION"
                    recognized = True
                else:
                    status = "REJECTED_REGISTRATION"

    body = {
        "type": "witnessed_registration_recovery",
        "version": 1,
        "status": status,
        "recognized": recognized,
        "registration_entry_idx": registration_entry_idx,
        "history_receipt_hash": history["receipt_hash"],
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_witnessed_registration_recovery_receipt(
    receipt: Mapping[str, Any],
) -> bool:
    """Check receipt integrity and internal consistency, not historical authenticity."""
    expected_fields = {
        "type",
        "version",
        "status",
        "recognized",
        "registration_entry_idx",
        "history_receipt_hash",
        "accepted",
        "truth_claimed",
        "write_authority",
        "execution_authority",
        "receipt_hash",
    }

    if type(receipt) is not dict or set(receipt) != expected_fields:
        return False

    # Rejected registrations preserve the supplied index, including malformed
    # values, as diagnostic evidence. Only non-rejected statuses require a
    # positive integer index. Receipt integrity does not authenticate history.
    status = receipt.get("status")
    if status not in {
        "REJECTED_HISTORY",
        "REJECTED_REGISTRATION",
        "VERIFIED_REGISTRATION",
    }:
        return False

    if (
        type(receipt.get("version")) is not int
        or receipt["version"] != 1
        or receipt.get("type") != "witnessed_registration_recovery"
        or type(receipt.get("recognized")) is not bool
        or receipt["recognized"] != (status == "VERIFIED_REGISTRATION")
        or (
            status != "REJECTED_REGISTRATION"
            and (
                type(receipt.get("registration_entry_idx")) is not int
                or receipt["registration_entry_idx"] < 1
            )
        )
        or type(receipt.get("history_receipt_hash")) is not str
        or not receipt["history_receipt_hash"]
        or receipt.get("accepted") is not False
        or receipt.get("truth_claimed") is not False
        or receipt.get("write_authority") != "NONE"
        or receipt.get("execution_authority") != "NONE"
        or type(receipt.get("receipt_hash")) is not str
    ):
        return False

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }

    try:
        return stable_hash(body) == receipt["receipt_hash"]
    except (ValueError, TypeError, RecursionError):
        return False



def evaluate_witnessed_reconstructed_registration(
    *,
    reconstructed_state: Mapping[str, Any],
    source_items: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    chain_path: str | Path,
    witness_path: str | Path,
    expected_chain_id: str,
    allowed_signers_path: str | Path,
    registration_entry_idx: int,
    registration_item: Mapping[str, Any],
    observation: Any,
) -> dict[str, Any]:
    """Require valid reconstruction and independently witnessed registration."""
    from holosim.reconstructor import (
        ReconstructionError,
        validate_reconstructed_state,
    )

    reconstruction_valid = False
    try:
        reconstruction_valid = validate_reconstructed_state(
            reconstructed_state, source_items
        )
    except (ReconstructionError, TypeError, ValueError, KeyError, IndexError):
        reconstruction_valid = False

    history_receipt = evaluate_witnessed_registration_recovery(
        chain_path=chain_path,
        witness_path=witness_path,
        expected_chain_id=expected_chain_id,
        allowed_signers_path=allowed_signers_path,
        registration_entry_idx=registration_entry_idx,
        registration_item=registration_item,
        observation=observation,
    )

    carried_matches = (
        reconstruction_valid
        and type(registration_item) is dict
        and registration_item in reconstructed_state["carried_items"]
    )

    recognized = (
        carried_matches
        and history_receipt["status"] == "VERIFIED_REGISTRATION"
        and history_receipt["recognized"] is True
    )

    body = {
        "type": "witnessed_reconstructed_registration",
        "version": 1,
        "status": (
            "VERIFIED_REGISTRATION"
            if recognized
            else "REJECTED_REGISTRATION"
        ),
        "recognized": bool(recognized),
        "reconstruction_valid": bool(reconstruction_valid),
        "registration_carried": bool(carried_matches),
        "history_status": history_receipt["status"],
        "history_receipt_hash": history_receipt["receipt_hash"],
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}



def verify_witnessed_reconstructed_registration_receipt(
    receipt: Mapping[str, Any],
) -> bool:
    """Verify internal receipt integrity, not historical authenticity."""
    expected_fields = {
        "type",
        "version",
        "status",
        "recognized",
        "reconstruction_valid",
        "registration_carried",
        "history_status",
        "history_receipt_hash",
        "accepted",
        "truth_claimed",
        "write_authority",
        "execution_authority",
        "receipt_hash",
    }
    if type(receipt) is not dict or set(receipt) != expected_fields:
        return False

    history_status = receipt.get("history_status")
    if history_status not in {
        "REJECTED_HISTORY",
        "REJECTED_REGISTRATION",
        "VERIFIED_REGISTRATION",
    }:
        return False

    recognized = receipt.get("recognized")
    reconstruction_valid = receipt.get("reconstruction_valid")
    registration_carried = receipt.get("registration_carried")

    if (
        type(recognized) is not bool
        or type(reconstruction_valid) is not bool
        or type(registration_carried) is not bool
        or (registration_carried and not reconstruction_valid)
    ):
        return False

    expected_recognition = (
        registration_carried
        and history_status == "VERIFIED_REGISTRATION"
    )

    if (
        receipt.get("type") != "witnessed_reconstructed_registration"
        or type(receipt.get("version")) is not int
        or receipt["version"] != 1
        or recognized != expected_recognition
        or receipt.get("status") != (
            "VERIFIED_REGISTRATION"
            if recognized
            else "REJECTED_REGISTRATION"
        )
        or type(receipt.get("history_receipt_hash")) is not str
        or not receipt["history_receipt_hash"]
        or receipt.get("accepted") is not False
        or receipt.get("truth_claimed") is not False
        or receipt.get("write_authority") != "NONE"
        or receipt.get("execution_authority") != "NONE"
        or type(receipt.get("receipt_hash")) is not str
    ):
        return False

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    try:
        return stable_hash(body) == receipt["receipt_hash"]
    except (ValueError, TypeError, RecursionError):
        return False
