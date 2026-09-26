"""Bind verified baseline content to the current persisted baseline head."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Callable

from holosim.bounded_baseline_content_identity import (
    verify_baseline_content_identity_receipt,
)
from holosim.persistent_baseline_transition import (
    PersistentBaselineTransitionStore,
)


RECEIPT_TYPE = "persistent_baseline_content_binding"
RECEIPT_VERSION = 1

CURRENT_BASELINE_BOUND = "CURRENT_BASELINE_BOUND"
CONTENT_BINDING_INCOMPLETE = "CONTENT_BINDING_INCOMPLETE"
BASELINE_ID_MISMATCH = "BASELINE_ID_MISMATCH"
BASELINE_STATE_IDENTITY_MISMATCH = "BASELINE_STATE_IDENTITY_MISMATCH"


class PersistentBaselineContentBindingError(ValueError):
    """Raised when persistent baseline binding inputs are malformed."""


def _hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bind_persistent_baseline_content(
    *,
    store: PersistentBaselineTransitionStore,
    content_identity_receipt: Mapping[str, Any],
    identity_function: Callable[[Any], Any],
) -> dict[str, Any]:
    """Bind one verified content identity receipt to the persisted current head.

    The persistent store is responsible for reconstructing and verifying its
    current baseline head. The content identity receipt is responsible for
    binding actual baseline content to a declared state identity.

    This function establishes only that those two independently checked
    identities refer to the same current baseline.

    It does not authorize persistence, compression, mutation, or truth claims.
    """

    if not isinstance(store, PersistentBaselineTransitionStore):
        raise PersistentBaselineContentBindingError(
            "store must be a PersistentBaselineTransitionStore"
        )

    if not isinstance(content_identity_receipt, Mapping):
        raise PersistentBaselineContentBindingError(
            "content_identity_receipt must be a mapping"
        )

    content_check = verify_baseline_content_identity_receipt(
        content_identity_receipt,
        identity_function=identity_function,
    )
    if not content_check["valid"]:
        raise PersistentBaselineContentBindingError(
            "content_identity_receipt must verify before persistent binding"
        )

    head = store.current_head()

    content_binding_complete = (
        content_identity_receipt.get("binding_complete") is True
    )
    baseline_id_matches = (
        content_identity_receipt.get("baseline_id")
        == head["baseline_id"]
    )
    state_identity_matches = (
        content_identity_receipt.get("declared_state_identity")
        == head["baseline_state_hash"]
    )

    if not content_binding_complete:
        status = CONTENT_BINDING_INCOMPLETE
    elif not baseline_id_matches:
        status = BASELINE_ID_MISMATCH
    elif not state_identity_matches:
        status = BASELINE_STATE_IDENTITY_MISMATCH
    else:
        status = CURRENT_BASELINE_BOUND

    binding_complete = (
        content_binding_complete
        and baseline_id_matches
        and state_identity_matches
    )

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "content_identity_receipt_id": content_identity_receipt[
            "receipt_id"
        ],
        "baseline_id": content_identity_receipt["baseline_id"],
        "declared_state_identity": content_identity_receipt[
            "declared_state_identity"
        ],
        "current_baseline_id": head["baseline_id"],
        "current_baseline_state_hash": head["baseline_state_hash"],
        "transition_count": head["transition_count"],
        "content_binding_complete": content_binding_complete,
        "baseline_id_matches": baseline_id_matches,
        "state_identity_matches": state_identity_matches,
        "binding_complete": binding_complete,
        "status": status,
        "baseline_truth_verified": False,
        "compression_preservation_verified": False,
        "compression_authorized": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {**body, "receipt_id": _hash(body)}