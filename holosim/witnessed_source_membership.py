"""Read-only source membership against independently witnessed chain history."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping
from holosim.canonical import stable_hash
from holosim.core import HoloChain
from holosim.witnessed_history_recovery import _recover_witnessed_history_with_entries

def verify_witnessed_source_membership(*, chain_path: str | Path, witness_path: str | Path, expected_chain_id: str, allowed_signers_path: str | Path, source_bindings: list[dict[str, Any]]) -> dict[str, Any]:
    status = "REJECTED_HISTORY"
    verified = False
    history_hash = None
    try:
        history, entries = _recover_witnessed_history_with_entries(chain_path=chain_path, witness_path=witness_path, expected_chain_id=expected_chain_id, allowed_signers_path=allowed_signers_path)
        history_hash = history.get("receipt_hash")
        if history.get("status") == "MATCHED" and history.get("matched") is True and entries is not None:
            observed = history.get("observed")
            if type(observed) is dict and type(observed.get("entry_count")) is int and type(observed.get("head_hash")) is str and observed["entry_count"] == len(entries) and observed["head_hash"] == (entries[-1]["hash"] if entries else "0" * 64):
                status = "REJECTED_SOURCE_MEMBERSHIP"
                if type(source_bindings) is list and source_bindings:
                    used = set()
                    valid = True
                    for binding in source_bindings:
                        if type(binding) is not dict or set(binding) != {"entry_idx", "source_item"}:
                            valid = False
                            break
                        idx = binding["entry_idx"]
                        item = binding["source_item"]
                        if type(idx) is not int or idx < 1 or idx > len(entries) or idx in used or type(item) is not dict:
                            valid = False
                            break
                        used.add(idx)
                        decoded = HoloChain._decode_entries([entries[idx - 1]])[0]
                        if type(decoded) is not dict or decoded != item:
                            valid = False
                            break
                    if valid:
                        status = "VERIFIED_SOURCE_MEMBERSHIP"
                        verified = True
    except (ValueError, TypeError, KeyError, IndexError, OSError, RecursionError):
        pass
    body = {"type": "witnessed_source_membership", "version": 1, "status": status, "verified": verified, "history_receipt_hash": history_hash, "accepted": False, "truth_claimed": False, "write_authority": "NONE", "execution_authority": "NONE"}
    return {**body, "receipt_hash": stable_hash(body)}
