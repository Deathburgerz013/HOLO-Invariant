"""PARTIAL exact-snapshot comparison against an external SSH witness."""
from __future__ import annotations

import base64
import json
import re
import subprocess
import tempfile
from pathlib import Path

from holosim.canonical import canonical_bytes, stable_hash
from holosim.core import HoloChain

NAMESPACE = "holo-history-witness-v1"
MAX_CHAIN_BYTES = 4_194_304
MAX_ENTRIES = 4096
MAX_WITNESS_BYTES = 16_384
FIELDS = {"type", "version", "namespace", "chain_id", "entry_count", "head_hash", "signer_identity"}


class HistoryWitnessError(ValueError):
    """Invalid input, snapshot, or unavailable signature tool."""


def _text(value):
    if type(value) is not str or not value.strip() or len(value) > 256 or "\n" in value or "\r" in value:
        raise HistoryWitnessError("invalid identifier")
    return value


def _read(path, limit):
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise HistoryWitnessError("input exceeds byte limit")
    return data


def _snapshot(path):
    # Verify the captured bytes, rather than rereading a moving source file.
    data = _read(path, MAX_CHAIN_BYTES)
    lines = [line for line in data.splitlines() if line.strip()]
    if len(lines) > MAX_ENTRIES:
        raise HistoryWitnessError("entry limit exceeded")
    for index, line in enumerate(lines, 1):
        entry = json.loads(line)
        if type(entry) is not dict or type(entry.get("idx")) is not int or entry["idx"] != index:
            raise HistoryWitnessError("invalid entry index")
        if any(type(entry.get(key)) is not str for key in ("timestamp", "content", "hash", "prev_hash")):
            raise HistoryWitnessError("invalid hashed field")
    with tempfile.TemporaryDirectory(prefix="holo-history-snapshot-") as folder:
        copy = Path(folder) / "chain.jsonl"
        copy.write_bytes(data)
        entries = HoloChain(copy).load_and_verify()
    return len(entries), entries[-1]["hash"] if entries else "0" * 64


def _run(args, data, tool):
    try:
        return subprocess.run([tool, *args], input=data, capture_output=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HistoryWitnessError("signature tool unavailable") from exc


def sign_history_witness(*, chain_path, chain_id, signer_identity, private_key_path, ssh_keygen="ssh-keygen"):
    """Return a signed commitment; caller retains it outside the chain."""
    count, head = _snapshot(chain_path)
    body = {"type": "history_witness", "version": 1, "namespace": NAMESPACE,
            "chain_id": _text(chain_id), "entry_count": count, "head_hash": head,
            "signer_identity": _text(signer_identity)}
    result = _run(["-Y", "sign", "-n", NAMESPACE, "-f", str(private_key_path)], canonical_bytes(body), ssh_keygen)
    if result.returncode or not result.stdout.startswith(b"-----BEGIN SSH SIGNATURE-----"):
        raise HistoryWitnessError("signing failed")
    return {**body, "signature": base64.b64encode(result.stdout).decode("ascii")}


def _witness(data):
    obj = json.loads(data)
    if type(obj) is not dict or set(obj) != FIELDS | {"signature"}:
        raise HistoryWitnessError("witness schema mismatch")
    if obj["type"] != "history_witness" or type(obj["version"]) is not int or obj["version"] != 1 or obj["namespace"] != NAMESPACE:
        raise HistoryWitnessError("witness contract mismatch")
    _text(obj["chain_id"])
    _text(obj["signer_identity"])
    if type(obj["entry_count"]) is not int or not 0 <= obj["entry_count"] <= MAX_ENTRIES:
        raise HistoryWitnessError("invalid entry count")
    if type(obj["head_hash"]) is not str or not re.fullmatch("[0-9a-f]{64}", obj["head_hash"]):
        raise HistoryWitnessError("invalid head hash")
    if type(obj["signature"]) is not str:
        raise HistoryWitnessError("invalid signature")
    signature = base64.b64decode(obj["signature"], validate=True)
    return obj, signature


def recover_witnessed_history(*, chain_path, witness_path, expected_chain_id, allowed_signers_path, ssh_keygen="ssh-keygen"):
    """Observe a match or explicit refusal. Does not authorize resume."""
    _text(expected_chain_id)
    status = "REJECTED_WITNESS"
    observed = None
    witness_hash = None
    try:
        if Path(chain_path).resolve() == Path(witness_path).resolve():
            raise HistoryWitnessError("chain and witness paths must differ")
        witness, signature = _witness(_read(witness_path, MAX_WITNESS_BYTES))
        witness_hash = stable_hash(witness)
        body = {key: witness[key] for key in FIELDS}
        status = "REJECTED_SIGNATURE"
        with tempfile.TemporaryDirectory(prefix="holo-history-verify-") as folder:
            sig = Path(folder) / "witness.sig"
            sig.write_bytes(signature)
            result = _run(["-Y", "verify", "-n", NAMESPACE, "-I", witness["signer_identity"],
                           "-f", str(allowed_signers_path), "-s", str(sig)], canonical_bytes(body), ssh_keygen)
        if result.returncode:
            status = "REJECTED_SIGNATURE"
        elif witness["chain_id"] != expected_chain_id:
            status = "REJECTED_CHAIN_ID"
        else:
            status = "REJECTED_CHAIN"
            count, head = _snapshot(chain_path)
            observed = {"entry_count": count, "head_hash": head}
            if count != witness["entry_count"]:
                status = "REJECTED_COUNT"
            elif head != witness["head_hash"]:
                status = "REJECTED_HEAD"
            else:
                status = "MATCHED"
    except FileNotFoundError:
        # The status indicates which phase failed; absence never skips a check.
        pass
    except (ValueError, OSError, RecursionError):
        pass
    body = {"type": "witnessed_history_recovery", "version": 1,
            "expected_chain_id": expected_chain_id, "status": status, "matched": status == "MATCHED",
            "observed": observed, "witness_hash": witness_hash, "accepted": False,
            "truth_claimed": False, "write_authority": "NONE", "execution_authority": "NONE"}
    return {**body, "receipt_hash": stable_hash(body)}
