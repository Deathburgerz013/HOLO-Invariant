"""Bounded verification of an externally pinned SSH signer policy."""

from __future__ import annotations

import hashlib
import hmac
import re
from pathlib import Path

MAX_POLICY_BYTES = 65_536


class SignerPolicyCustodyError(ValueError):
    """The signer policy cannot be verified against its supplied anchor."""


def capture_pinned_signer_policy(
    *,
    allowed_signers_path: str | Path,
    expected_sha256: str,
) -> bytes:
    """Capture policy bytes only when they match an external digest.

    The caller is responsible for independently authenticating expected_sha256.
    This function does not establish provenance or grant authority.
    """
    if (
        type(expected_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
    ):
        raise SignerPolicyCustodyError("invalid expected policy digest")

    try:
        with Path(allowed_signers_path).open("rb") as stream:
            data = stream.read(MAX_POLICY_BYTES + 1)
    except OSError as exc:
        raise SignerPolicyCustodyError("policy unavailable") from exc

    if not data or len(data) > MAX_POLICY_BYTES:
        raise SignerPolicyCustodyError("invalid policy size")

    actual = hashlib.sha256(data).hexdigest()

    if not hmac.compare_digest(actual, expected_sha256):
        raise SignerPolicyCustodyError("policy digest mismatch")

    return data
