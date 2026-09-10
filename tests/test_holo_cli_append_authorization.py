"""Regression test for the CLI -> typed authorization boundary.

The canonical CLI accepts reviewer and approval-reference arguments, while
HoloService requires a typed, target-bound operational authorization.

The CLI is responsible for adapting those operator-supplied fields into the
typed SERVICE_APPEND authorization before calling HoloService.append().
"""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from holosim import holo_cli
from holosim.typed_operational_authorization import (
    ACTION_SERVICE_APPEND,
    validate_operational_authorization,
)


def test_cli_append_builds_typed_service_authorization(
    monkeypatch,
) -> None:
    content = "authority boundary probe"
    reviewer = "test-reviewer"
    approval_reference = "test-approval"

    canonical = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    target_sha256 = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    observed: dict[str, Any] = {}

    class RecordingService:
        def append(
            self,
            value: Any,
            *,
            compress: bool = True,
            mirror_to_slots: bool = False,
            tier: str = "standard",
            authorization=None,
        ) -> dict[str, Any]:
            assert value == content
            assert authorization is not None

            validate_operational_authorization(
                authorization,
                expected_action=ACTION_SERVICE_APPEND,
                expected_target_sha256=target_sha256,
            )

            observed["authorization"] = dict(authorization)

            return {
                "status": "COMMITTED",
                "commit_performed": True,
            }

    monkeypatch.setattr(
        holo_cli,
        "get_service",
        lambda _path: RecordingService(),
    )

    args = argparse.Namespace(
        file="unused-test-chain.jsonl",
        text=content,
        no_compress=False,
        mirror_slots=False,
        tier="standard",
        reviewer=reviewer,
        approval_reference=approval_reference,
    )

    result = holo_cli.run_service_append(args)

    assert result == 0
    assert observed["authorization"]["actor_id"] == reviewer
    assert (
        observed["authorization"]["approval_reference"]
        == approval_reference
    )
    assert (
        observed["authorization"]["action"]
        == ACTION_SERVICE_APPEND
    )
    assert (
        observed["authorization"]["target_sha256"]
        == target_sha256
    )
