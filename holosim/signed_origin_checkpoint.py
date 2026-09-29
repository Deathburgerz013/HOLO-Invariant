"""Research-only public-key binding for one admitted Spine candidate.

An external trust policy supplies the allowed signers file. A valid SSH
signature proves control of that key over these exact bytes and receipt;
it does not prove authorship, truth, currentness, or operational authority.
"""

from __future__ import annotations

import base64
import binascii
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from holosim.canonical import canonical_bytes, stable_hash
from holosim.spine_admission import (
    build_spine_admission_receipt,
    validate_spine_admission_receipt,
)

NAMESPACE = "holo-origin-checkpoint-v1"
CHECKPOINT_TYPE = "signed_origin_checkpoint"
BODY_FIELDS = {
    "type", "version", "candidate_source_sha256", "admission_receipt_hash",
    "validator_id", "contributor_id", "signer_identity", "namespace",
}


class SignedOriginCheckpointError(ValueError):
    """Raised when the signed checkpoint cannot be constructed or checked."""


def _candidate_text(candidate: bytes) -> str:
    if type(candidate) is not bytes:
        raise SignedOriginCheckpointError("candidate must be exact UTF-8 bytes")
    try:
        return candidate.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SignedOriginCheckpointError("candidate must be UTF-8") from exc


def _admission(candidate: bytes, validator_id: str, contributor_id: str | None) -> dict[str, Any]:
    receipt = build_spine_admission_receipt(
        _candidate_text(candidate), validator_id=validator_id,
        contributor_id=contributor_id,
    )
    if receipt["decision"] != "ADMITTED":
        raise SignedOriginCheckpointError("candidate failed Spine admission")
    validate_spine_admission_receipt(receipt)
    return receipt


def _body(candidate: bytes, receipt: Mapping[str, Any], signer_identity: str,
          contributor_id: str | None) -> dict[str, Any]:
    if type(signer_identity) is not str or not signer_identity.strip():
        raise SignedOriginCheckpointError("signer_identity must be nonempty")
    return {
        "type": CHECKPOINT_TYPE,
        "version": 1,
        "candidate_source_sha256": receipt["candidate_source_sha256"],
        "admission_receipt_hash": receipt["receipt_hash"],
        "validator_id": receipt["validator_id"],
        "contributor_id": contributor_id,
        "signer_identity": signer_identity,
        "namespace": NAMESPACE,
    }


def _run(args: list[str], *, data: bytes, ssh_keygen: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            [ssh_keygen, *args], input=data, capture_output=True, check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SignedOriginCheckpointError("SSH signature tool unavailable") from exc


def sign_origin_checkpoint(*, candidate: bytes, validator_id: str,
                           contributor_id: str | None, signer_identity: str,
                           private_key_path: str | Path,
                           ssh_keygen: str = "ssh-keygen") -> dict[str, Any]:
    """Sign exact admitted candidate identity using a caller-owned SSH key."""
    receipt = _admission(candidate, validator_id, contributor_id)
    body = _body(candidate, receipt, signer_identity, contributor_id)
    message = canonical_bytes(body)
    result = _run(
        ["-Y", "sign", "-n", NAMESPACE, "-f", str(private_key_path)],
        data=message, ssh_keygen=ssh_keygen,
    )
    if result.returncode != 0 or not result.stdout.startswith(b"-----BEGIN SSH SIGNATURE-----"):
        raise SignedOriginCheckpointError("SSH signing failed")
    return {
        **body,
        "signature": base64.b64encode(result.stdout).decode("ascii"),
    }


def verify_origin_checkpoint(*, candidate: bytes, checkpoint: Mapping[str, Any],
                             allowed_signers_path: str | Path,
                             ssh_keygen: str = "ssh-keygen") -> dict[str, Any]:
    """Verify against an independently supplied signer policy and fresh admission."""
    if type(checkpoint) is not dict or set(checkpoint) != BODY_FIELDS | {"signature"}:
        raise SignedOriginCheckpointError("checkpoint schema mismatch")
    if checkpoint["type"] != CHECKPOINT_TYPE or type(checkpoint["version"]) is not int or checkpoint["version"] != 1:
        raise SignedOriginCheckpointError("checkpoint type or version invalid")
    if checkpoint["namespace"] != NAMESPACE:
        raise SignedOriginCheckpointError("checkpoint namespace mismatch")
    contributor_id = checkpoint["contributor_id"]
    if contributor_id is not None and (type(contributor_id) is not str or not contributor_id.strip()):
        raise SignedOriginCheckpointError("contributor_id invalid")
    receipt = _admission(candidate, checkpoint["validator_id"], contributor_id)
    expected = _body(candidate, receipt, checkpoint["signer_identity"], contributor_id)
    if any(checkpoint[key] != value for key, value in expected.items()):
        status = "REJECTED_BINDING"
    else:
        try:
            signature = base64.b64decode(checkpoint["signature"], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise SignedOriginCheckpointError("signature encoding invalid") from exc
        with tempfile.TemporaryDirectory(prefix="holo-origin-check-") as folder:
            sig_path = Path(folder) / "checkpoint.sig"
            sig_path.write_bytes(signature)
            result = _run(
                ["-Y", "verify", "-n", NAMESPACE, "-I", expected["signer_identity"],
                 "-f", str(allowed_signers_path), "-s", str(sig_path)],
                data=canonical_bytes(expected), ssh_keygen=ssh_keygen,
            )
        status = "VERIFIED" if result.returncode == 0 else "REJECTED_SIGNATURE"
    body = {
        "type": "signed_origin_checkpoint_verification", "version": 1,
        "candidate_source_sha256": receipt["candidate_source_sha256"],
        "admission_receipt_hash": receipt["receipt_hash"],
        "signer_identity": expected["signer_identity"],
        "status": status, "verified": status == "VERIFIED",
        "accepted": False, "truth_claimed": False,
        "write_authority": "NONE", "execution_authority": "NONE",
    }
    return {**body, "verification_hash": stable_hash(body)}
