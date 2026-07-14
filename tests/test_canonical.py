from datetime import datetime, timezone
from pathlib import Path

import pytest

from holosim.canonical import (
    CANONICAL_TYPE,
    CANONICAL_VERSION,
    CanonicalValueError,
    canonical_bytes,
    canonical_json,
    identity_packet,
    stable_hash,
)


def test_object_key_order_does_not_change_identity():
    left = {
        "environment": "lab",
        "observed": {"temperature": 21.5, "stable": True},
        "missing": [],
    }
    right = {
        "missing": [],
        "observed": {"stable": True, "temperature": 21.5},
        "environment": "lab",
    }

    assert canonical_json(left) == canonical_json(right)
    assert canonical_bytes(left) == canonical_bytes(right)
    assert stable_hash(left) == stable_hash(right)


def test_list_order_remains_identity_significant():
    first = {"observation_hashes": ["a", "b"]}
    second = {"observation_hashes": ["b", "a"]}

    assert stable_hash(first) != stable_hash(second)


def test_canonical_json_preserves_unicode_without_spacing_noise():
    value = {"anchor": "Canyon", "symbol": "Ω", "values": [1, 2]}

    assert canonical_json(value) == (
        '{"anchor":"Canyon","symbol":"Ω","values":[1,2]}'
    )


@pytest.mark.parametrize(
    "value",
    [
        {"unsupported": {"set"}},
        {"unsupported": (1, 2)},
        {"unsupported": b"bytes"},
        {"unsupported": Path("evidence.json")},
        {"unsupported": datetime.now(timezone.utc)},
        {1: "non-string-key"},
        {"number": float("nan")},
        {"number": float("inf")},
        {"number": float("-inf")},
    ],
)
def test_unsupported_or_ambiguous_values_are_rejected(value):
    with pytest.raises(CanonicalValueError):
        canonical_json(value)


def test_identity_packet_is_full_hash_and_non_authoritative():
    value = {"observed_at": "2026-07-14T23:30:00Z"}

    packet = identity_packet(value)

    assert packet == {
        "type": CANONICAL_TYPE,
        "version": CANONICAL_VERSION,
        "algorithm": "sha256",
        "sha256": stable_hash(value),
        "canonical_size_bytes": len(canonical_bytes(value)),
        "write_authority": "NONE",
    }
    assert len(packet["sha256"]) == 64


def test_caller_supplied_time_is_hashed_but_no_time_is_invented():
    without_time = {"environment_id": "lab"}
    with_time = {
        "environment_id": "lab",
        "observed_at": "2026-07-14T23:30:00Z",
    }

    assert "observed_at" not in canonical_json(without_time)
    assert stable_hash(without_time) != stable_hash(with_time)