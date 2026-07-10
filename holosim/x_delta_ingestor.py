"""Human-gated X thread delta ingestor for Holo/Sim.

Transforms exported public X posts into deterministic review packets.

Collection and persistence remain separate:

    extract -> review -> explicitly approve -> append

This module does not fetch from X, does not infer verification, and does not
write to HoloChain unless commit_reviewed() is called with approved=True.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

try:
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.core import HoloChain
    from holosim.generalizer import get_generalizer
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import DEFAULT_CHAIN_FILE
    from holosim.core import HoloChain
    from holosim.generalizer import get_generalizer


INGESTOR_TYPE = "x_delta_ingestor"
INGESTOR_VERSION = "0.2"

CRITICAL_TERMS = (
    "anchor",
    "continuity",
    "fixed point",
    "hash",
    "invariant",
    "merkle",
    "persistence",
    "provenance",
    "spine",
    "verified",
)

STRUCTURAL_PATTERNS = (
    "(c + i + e)^2",
    "(c+i+e)^2",
    "(c + i + e)²",
    "g(x+1)",
    "g(x + 1)",
)


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible content deterministically."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def stable_hash(value: Any) -> str:
    """Return a deterministic SHA-256 digest."""
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def normalize_posts(
    raw_thread_data: Sequence[Mapping[str, Any]] | Mapping[str, Any] | str,
) -> List[Dict[str, Any]]:
    """Normalize supported JSON exports into a list of post dictionaries."""
    parsed: Any = raw_thread_data

    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except json.JSONDecodeError as exc:
            raise ValueError("raw_thread_data must contain valid JSON.") from exc

    if isinstance(parsed, Mapping):
        for key in ("posts", "tweets", "data", "thread"):
            candidate = parsed.get(key)
            if isinstance(candidate, list):
                parsed = candidate
                break
        else:
            parsed = [parsed]

    if not isinstance(parsed, list):
        raise TypeError(
            "Thread data must resolve to a post object or a list of posts."
        )

    posts: List[Dict[str, Any]] = []

    for index, post in enumerate(parsed, start=1):
        if not isinstance(post, Mapping):
            raise TypeError(f"Post {index} is not a JSON object.")

        content = (
            post.get("content")
            or post.get("text")
            or post.get("full_text")
            or ""
        )

        normalized = {
            "id": str(
                post.get("id")
                or post.get("post_id")
                or post.get("tweet_id")
                or index
            ),
            "content": str(content).strip(),
        }

        for key in ("author", "created_at", "url"):
            if post.get(key) is not None:
                normalized[key] = post[key]

        posts.append(normalized)

    return posts


class XDeltaIngestor:
    """Extract, review, and explicitly persist public thread deltas."""

    def __init__(
        self,
        chain_path: str | Path = DEFAULT_CHAIN_FILE,
    ) -> None:
        self.chain_path = Path(chain_path)
        self.chain = HoloChain(str(self.chain_path))
        self.generalizer = get_generalizer()

    def classify_post(
        self,
        post: Mapping[str, Any],
        *,
        thread_ref: str,
    ) -> Dict[str, Any]:
        """Classify one post and preserve the evidence used."""
        content = str(post.get("content", "")).strip()
        lowered = content.lower()

        matched_terms = sorted(
            term for term in CRITICAL_TERMS if term in lowered
        )
        matched_patterns = sorted(
            pattern
            for pattern in STRUCTURAL_PATTERNS
            if pattern in lowered
        )

        generalization = self.generalizer.process(
            content,
            source="x_delta_ingestor",
            thread_id=thread_ref,
            tags=("x", "public_thread"),
        )

        tier = (
            "critical"
            if matched_terms or matched_patterns
            else "standard"
        )

        return {
            "post_id": str(post.get("id", "")),
            "tier": tier,
            "content": content,
            "content_hash": stable_hash(content),
            "matched_terms": matched_terms,
            "matched_patterns": matched_patterns,
            "routes": generalization.get("routes", []),
            "patterns": generalization.get("patterns", []),
            "generalization_hash": generalization.get(
                "generalization_hash"
            ),
        }

    def extract_deltas(
        self,
        raw_thread_data: Sequence[Mapping[str, Any]]
        | Mapping[str, Any]
        | str,
        thread_ref: str,
    ) -> Dict[str, Any]:
        """Create a deterministic review packet without persistence."""
        if not thread_ref.strip():
            raise ValueError("thread_ref cannot be empty.")

        posts = normalize_posts(raw_thread_data)
        classified = [
            self.classify_post(post, thread_ref=thread_ref)
            for post in posts
        ]

        critical = [
            post for post in classified if post["tier"] == "critical"
        ]
        standard = [
            post for post in classified if post["tier"] == "standard"
        ]

        source_hash = stable_hash(posts)

        packet: Dict[str, Any] = {
            "type": "x_delta_review_packet",
            "version": INGESTOR_VERSION,
            "thread_ref": thread_ref,
            "source_hash": source_hash,
            "post_count": len(posts),
            "critical": critical,
            "standard": standard,
            "archive_raw": posts,
            "verification": {
                "status": "review_pending",
                "human_approved": False,
            },
            "timestamp": utc_now(),
        }

        hashable_packet = {
            key: value
            for key, value in packet.items()
            if key not in {"archive_raw", "timestamp"}
        }
        packet["review_hash"] = stable_hash(hashable_packet)

        return packet

    def prepare_commit(
        self,
        review_packet: Mapping[str, Any],
        *,
        reviewer: str,
    ) -> Dict[str, Any]:
        """Prepare the exact payload that would enter HoloChain."""
        if review_packet.get("type") != "x_delta_review_packet":
            raise ValueError("Unsupported review packet type.")

        if not reviewer.strip():
            raise ValueError("reviewer cannot be empty.")

        return {
            "type": "x_delta_ingest",
            "version": INGESTOR_VERSION,
            "thread_ref": review_packet.get("thread_ref"),
            "source_hash": review_packet.get("source_hash"),
            "review_hash": review_packet.get("review_hash"),
            "post_count": review_packet.get("post_count", 0),
            "critical": list(review_packet.get("critical", [])),
            "standard": list(review_packet.get("standard", [])),
            "verification": {
                "status": "human_approved",
                "human_approved": True,
                "reviewer": reviewer,
                "approved_at": utc_now(),
            },
        }

    def commit_reviewed(
        self,
        review_packet: Mapping[str, Any],
        *,
        reviewer: str,
        approved: bool = False,
    ) -> Dict[str, Any]:
        """Append only after explicit human approval."""
        if not approved:
            return {
                "status": "review_pending",
                "appended": False,
                "thread_ref": review_packet.get("thread_ref"),
                "review_hash": review_packet.get("review_hash"),
                "message": "Explicit approval is required before append.",
            }

        verify_before = self.chain.load_and_verify()
        payload = self.prepare_commit(
            review_packet,
            reviewer=reviewer,
        )

        append_result = self.chain.append(canonical_json(payload))
        verify_after = self.chain.load_and_verify()

        return {
            "status": "committed",
            "appended": True,
            "thread_ref": payload["thread_ref"],
            "review_hash": payload["review_hash"],
            "payload_hash": stable_hash(payload),
            "entries_before": len(verify_before),
            "entries_after": len(verify_after),
            "append": append_result,
        }

    def extract_file(
        self,
        source_file: str | Path,
        *,
        thread_ref: str,
    ) -> Dict[str, Any]:
        """Read a local JSON export and create a review packet."""
        path = Path(source_file)

        if not path.is_file():
            raise FileNotFoundError(f"Thread export not found: {path}")

        return self.extract_deltas(
            path.read_text(encoding="utf-8"),
            thread_ref,
        )


def get_x_ingestor(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
) -> XDeltaIngestor:
    """Create an X delta ingestor."""
    return XDeltaIngestor(chain_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract and review public X thread deltas."
    )
    parser.add_argument(
        "--file",
        "-f",
        default=str(DEFAULT_CHAIN_FILE),
        help="HoloChain JSONL path",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract a JSON thread export without appending",
    )
    extract_parser.add_argument("source_file")
    extract_parser.add_argument("--thread-ref", required=True)
    extract_parser.add_argument(
        "--output",
        default=None,
        help="Optional review packet output file",
    )

    commit_parser = subparsers.add_parser(
        "commit",
        help="Commit an already reviewed packet",
    )
    commit_parser.add_argument("review_file")
    commit_parser.add_argument("--reviewer", required=True)
    commit_parser.add_argument(
        "--approved",
        action="store_true",
        help="Explicitly authorize persistence",
    )

    args = parser.parse_args()
    ingestor = get_x_ingestor(args.file)

    if args.command == "extract":
        result = ingestor.extract_file(
            args.source_file,
            thread_ref=args.thread_ref,
        )

        if args.output:
            Path(args.output).write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    elif args.command == "commit":
        review_packet = json.loads(
            Path(args.review_file).read_text(encoding="utf-8")
        )
        result = ingestor.commit_reviewed(
            review_packet,
            reviewer=args.reviewer,
            approved=args.approved,
        )

    else:
        raise SystemExit(f"Unknown command: {args.command}")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()