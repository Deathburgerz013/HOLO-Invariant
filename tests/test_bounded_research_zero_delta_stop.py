"""Composition test for bounded re-search with a zero-delta stop.

The canonical Holo/Sim header may act as a retrieval cue. Retrieval itself
grants no provenance, truth, acceptance, write, or execution authority.

This test asks the smaller question first:

Can the existing deterministic query identity support a bounded re-search
cycle that continues only while relevant retrieved evidence changes and stops
once a repeated pass produces no delta?

If yes, no new production boundary is warranted by this case alone.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from holosim.agent_runtime import HoloAgentRuntime


HEADER = "| | █†█ Holo/Sim █†█ █†█HSSCE█†█"


def _document(path: str, content: str) -> dict[str, Any]:
    return {
        "path": path,
        "name": path.rsplit("/", 1)[-1],
        "suffix": ".md",
        "chars": len(content),
        "content_hash": hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest(),
        "content": content,
    }


class _SnapshotSource:
    """Supply declared document snapshots and count actual search passes."""

    def __init__(
        self,
        snapshots: list[list[dict[str, Any]]],
    ) -> None:
        self.snapshots = snapshots
        self.calls = 0

    def discover_documents(self) -> list[dict[str, Any]]:
        index = min(self.calls, len(self.snapshots) - 1)
        self.calls += 1
        return self.snapshots[index]


def _query(source: _SnapshotSource) -> dict[str, Any]:
    # Exercise the real production query implementation without constructing
    # the rest of HoloAgentRuntime. query_spines only requires the declared
    # discover_documents boundary.
    return HoloAgentRuntime.query_spines(
        source,
        HEADER,
        limit=5,
    )


def _bounded_research(
    query_once: Callable[[], dict[str, Any]],
    *,
    max_passes: int = 8,
) -> dict[str, Any]:
    """Test-only composition of existing query identities.

    A first pass establishes a result identity.
    A changed identity warrants another comparison pass.
    A repeated identity establishes zero observed retrieval delta and stops.

    This helper is intentionally not production code.
    """
    previous_hash: str | None = None
    observed_hashes: list[str] = []

    for pass_number in range(1, max_passes + 1):
        result = query_once()
        current_hash = result["query_hash"]
        observed_hashes.append(current_hash)

        if previous_hash == current_hash:
            return {
                "passes": pass_number,
                "observed_hashes": observed_hashes,
                "terminal_reason": "NO_RELEVANT_RESEARCH_DELTA",
                "research_warranted": False,
                "truth_claimed": False,
                "accepted": False,
                "write_authority": "NONE",
                "execution_authority": "NONE",
            }

        previous_hash = current_hash

    return {
        "passes": max_passes,
        "observed_hashes": observed_hashes,
        "terminal_reason": "PASS_BOUND_EXHAUSTED",
        "research_warranted": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


def test_unchanged_research_identity_stops_after_confirmation_pass() -> None:
    content = f"""
{HEADER}

# Spine Header Invariant

The header is a recognition primitive.

It signals:

Search for this protocol.
""".strip()

    snapshot = [
        _document(
            "docs/SPINE_BOUNDARY_SPEC.md",
            content,
        )
    ]

    source = _SnapshotSource(
        [
            snapshot,
            snapshot,
            snapshot,
        ]
    )

    result = _bounded_research(
        lambda: _query(source),
        max_passes=8,
    )

    assert result["terminal_reason"] == "NO_RELEVANT_RESEARCH_DELTA"

    # One pass establishes the retrieved state.
    # One identical pass establishes observed delta == 0.
    # A third search is not warranted.
    assert result["passes"] == 2
    assert source.calls == 2

    assert len(result["observed_hashes"]) == 2
    assert (
        result["observed_hashes"][0]
        == result["observed_hashes"][1]
    )

    assert result["research_warranted"] is False
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_real_retrieval_delta_continues_until_next_unchanged_pass() -> None:
    first_content = f"""
{HEADER}

# Spine Header Invariant

The header is a recognition primitive.

It signals:

Search for this protocol.
""".strip()

    changed_content = f"""
{HEADER}

# Spine Header Invariant

The header is a recognition primitive.

It signals:

Search for this protocol.

# Header Pointer Invariant

The header points toward the protocol required for reconstruction.
Its purpose is recognition, not storage.
""".strip()

    first_snapshot = [
        _document(
            "docs/SPINE_BOUNDARY_SPEC.md",
            first_content,
        )
    ]

    changed_snapshot = [
        _document(
            "docs/SPINE_BOUNDARY_SPEC.md",
            changed_content,
        )
    ]

    source = _SnapshotSource(
        [
            first_snapshot,
            changed_snapshot,
            changed_snapshot,
            changed_snapshot,
        ]
    )

    result = _bounded_research(
        lambda: _query(source),
        max_passes=8,
    )

    # Pass 2 contains an actual changed retrieval identity, so stopping there
    # would be premature. Pass 3 repeats pass 2 and establishes zero delta.
    assert result["passes"] == 3
    assert source.calls == 3

    hashes = result["observed_hashes"]

    assert hashes[0] != hashes[1]
    assert hashes[1] == hashes[2]

    assert result["terminal_reason"] == "NO_RELEVANT_RESEARCH_DELTA"
    assert result["research_warranted"] is False
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"