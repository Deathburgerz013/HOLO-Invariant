"""Bounded comparison against a separately provisioned policy digest.

The reference's provenance must be established outside this module.
A matching digest does not authenticate its source or grant authority.
"""

from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from typing import Literal


Status = Literal["MATCHED", "MISMATCH", "UNKNOWN"]
SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class PolicyAnchorResult:
    status: Status
    reference_available: bool
    provenance_authenticated: bool = False
    accepted: bool = False
    truth_claimed: bool = False
    write_authority: str = "NONE"
    execution_authority: str = "NONE"
    trust_root_authority: str = "NONE"


def compare_policy_anchor(
    *,
    proposed_sha256: str,
    provisioned_sha256: str | None,
) -> PolicyAnchorResult:
    """Compare digests without authenticating the provisioned reference."""
    if type(proposed_sha256) is not str or SHA256.fullmatch(proposed_sha256) is None:
        raise ValueError("invalid proposed digest")

    if provisioned_sha256 is None:
        return PolicyAnchorResult("UNKNOWN", False)

    if (
        type(provisioned_sha256) is not str
        or SHA256.fullmatch(provisioned_sha256) is None
    ):
        raise ValueError("invalid provisioned digest")

    status: Status = (
        "MATCHED"
        if hmac.compare_digest(proposed_sha256, provisioned_sha256)
        else "MISMATCH"
    )
    return PolicyAnchorResult(status, True)
