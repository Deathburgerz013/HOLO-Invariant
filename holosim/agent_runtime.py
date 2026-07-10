"""Read-only proposal runtime for Holo/Sim.

The agent runtime may:

- verify and observe the canonical HoloChain
- inspect repository spine documents
- generalize goals across domain spines
- construct deterministic action proposals
- export proposals for human review

The agent runtime may not:

- append to HoloChain
- invoke rebirth
- create genesis state
- mutate slot databases
- silently record sessions
- interpret a natural-language goal as write authorization

Persistence must occur through a separate reviewed commit boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

try:
    from holosim.api import get_api
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HOLOSIM_VERSION,
        REPO_ROOT,
    )
    from holosim.generalizer import get_generalizer
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from holosim.api import get_api
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HOLOSIM_VERSION,
        REPO_ROOT,
    )
    from holosim.generalizer import get_generalizer


AGENT_TYPE = "holo_agent_runtime"
AGENT_VERSION = "0.1"
PROPOSAL_TYPE = "holo_agent_proposal"
PROPOSAL_VERSION = "0.1"

DEFAULT_DOCUMENT_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".py",
}

SKIP_DIRECTORIES = {
    ".git",
    ".github",
    ".hypothesis",
    ".pytest_cache",
    ".venv",
    "venv",
    "__pycache__",
    "archives",
    "test_archives",
    "runtime_watch",
}

WRITE_INTENT_TERMS = {
    "add",
    "append",
    "commit",
    "delete",
    "edit",
    "ingest",
    "insert",
    "remember",
    "remove",
    "save",
    "store",
    "update",
    "write",
}

VERIFY_INTENT_TERMS = {
    "audit",
    "check",
    "health",
    "integrity",
    "status",
    "tamper",
    "verify",
}

SEARCH_INTENT_TERMS = {
    "find",
    "knowledge",
    "query",
    "research",
    "search",
    "spine",
}

RECOVERY_INTENT_TERMS = {
    "rebirth",
    "recover",
    "recovery",
    "reset",
    "rollback",
}
SEARCH_STOPWORDS = {
    "a",
    "an",
    "and",
    "append",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "new",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


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


def tokenize(text: str) -> List[str]:
    """Return normalized search tokens."""
    return re.findall(r"[a-z0-9_+\-^]+", text.lower())


def git_snapshot(repo_root: Path) -> Dict[str, Optional[str]]:
    """Read Git identity without modifying the repository."""
    result: Dict[str, Optional[str]] = {
        "branch": None,
        "commit": None,
        "dirty": None,
    }

    try:
        result["branch"] = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or None
    except Exception:
        pass

    try:
        result["commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or None
    except Exception:
        pass

    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        result["dirty"] = "true" if status.strip() else "false"
    except Exception:
        pass

    return result


class ReadOnlyViolation(RuntimeError):
    """Raised when a request attempts to cross the write boundary."""


class HoloAgentRuntime:
    """Read-only observation and proposal engine."""

    def __init__(
        self,
        chain_path: str | Path = DEFAULT_CHAIN_FILE,
        *,
        repo_root: str | Path = REPO_ROOT,
        thread_id: Optional[str] = None,
    ) -> None:
        self.chain_path = Path(chain_path)
        self.repo_root = Path(repo_root).resolve()
        self.thread_id = thread_id

        self.api = get_api(self.chain_path)
        self.generalizer = get_generalizer()

        self._documents: Optional[List[Dict[str, Any]]] = None

    def identity(self) -> Dict[str, Any]:
        """Return agent identity and enforced capabilities."""
        return {
            "type": AGENT_TYPE,
            "version": AGENT_VERSION,
            "mode": "read_only",
            "anchor": ANCHOR,
            "active_hash": ACTIVE_HASH,
            "holosim_version": HOLOSIM_VERSION,
            "thread_id": self.thread_id,
            "chain_file": str(self.chain_path),
            "repo_root": str(self.repo_root),
            "git": git_snapshot(self.repo_root),
            "capabilities": [
                "identity",
                "observe",
                "verify",
                "query_spines",
                "plan",
                "propose",
            ],
            "prohibited": [
                "append_chain",
                "commit_proposal",
                "invoke_rebirth",
                "mutate_database",
                "auto_genesis",
                "silent_session_logging",
            ],
        }

    def verify(self) -> Dict[str, Any]:
        """Verify canonical persistence through the stable internal API."""
        result = self.api.verify()

        return {
            "type": "holo_agent_verification",
            "agent_version": AGENT_VERSION,
            "read_only": True,
            "result": result,
            "timestamp": utc_now(),
        }

    def observe(
        self,
        *,
        last: int = 5,
        include_health: bool = True,
    ) -> Dict[str, Any]:
        """Observe verified chain state without mutation."""
        if last <= 0:
            raise ValueError("last must be greater than zero.")

        verification = self.api.verify()
        replay = self.api.replay(last=last)

        result: Dict[str, Any] = {
            "type": "holo_agent_observation",
            "agent_version": AGENT_VERSION,
            "read_only": True,
            "thread_id": self.thread_id,
            "verification": verification,
            "replay": replay,
            "timestamp": utc_now(),
        }

        if include_health:
            result["health"] = self.api.health()

        result["observation_hash"] = stable_hash(
            {
                key: value
                for key, value in result.items()
                if key not in {"timestamp", "observation_hash"}
            }
        )

        return result

    def discover_documents(
        self,
        *,
        refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """Discover readable project documents without changing them."""
        if self._documents is not None and not refresh:
            return list(self._documents)

        documents: List[Dict[str, Any]] = []

        for path in sorted(self.repo_root.rglob("*")):
            if not path.is_file():
                continue

            try:
                relative = path.relative_to(self.repo_root)
            except ValueError:
                continue

            if any(part in SKIP_DIRECTORIES for part in relative.parts):
                continue

            if path.suffix.lower() not in DEFAULT_DOCUMENT_SUFFIXES:
                continue

            try:
                text = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            documents.append(
                {
                    "path": relative.as_posix(),
                    "name": path.name,
                    "suffix": path.suffix.lower(),
                    "chars": len(text),
                    "content_hash": hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest(),
                    "content": text,
                }
            )

        self._documents = documents
        return list(documents)

    def query_spines(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Search project documents using deterministic lexical scoring."""
        clean_query = query.strip()

        if not clean_query:
            raise ValueError("query cannot be empty.")

        if limit <= 0:
            raise ValueError("limit must be greater than zero.")

        query_tokens = {
            token
            for token in tokenize(clean_query)
            if token not in SEARCH_STOPWORDS and len(token) > 1
        }

        results: List[Dict[str, Any]] = []

        for document in self.discover_documents():
            content = str(document["content"])
            lowered = content.lower()
            name_lower = str(document["name"]).lower()

            token_hits = sorted(
                token
                for token in query_tokens
                if token in lowered or token in name_lower
            )

            phrase_hit = clean_query.lower() in lowered
            score = len(token_hits)

            if phrase_hit:
                score += 3

            if "spine" in name_lower:
                score += 1

            if score <= 0:
                continue

            match_position = -1

            if phrase_hit:
                match_position = lowered.find(clean_query.lower())
            elif token_hits:
                positions = [
                    lowered.find(token)
                    for token in token_hits
                    if lowered.find(token) >= 0
                ]
                if positions:
                    match_position = min(positions)

            if match_position < 0:
                match_position = 0

            start = max(0, match_position - 180)
            end = min(len(content), match_position + 520)

            snippet = content[start:end].strip()

            results.append(
                {
                    "path": document["path"],
                    "score": score,
                    "evidence": token_hits,
                    "phrase_match": phrase_hit,
                    "snippet": snippet,
                    "content_hash": document["content_hash"],
                }
            )

        results.sort(
            key=lambda item: (
                -int(item["score"]),
                str(item["path"]),
            )
        )

        packet = {
            "type": "holo_agent_query",
            "agent_version": AGENT_VERSION,
            "query": clean_query,
            "result_count": min(len(results), limit),
            "results": results[:limit],
            "timestamp": utc_now(),
        }

        packet["query_hash"] = stable_hash(
            {
                key: value
                for key, value in packet.items()
                if key not in {"timestamp", "query_hash"}
            }
        )

        return packet

    def classify_intent(self, goal: str) -> Dict[str, Any]:
        """Classify a goal without treating it as authorization."""
        tokens = set(tokenize(goal))

        write_hits = sorted(tokens.intersection(WRITE_INTENT_TERMS))
        verify_hits = sorted(tokens.intersection(VERIFY_INTENT_TERMS))
        search_hits = sorted(tokens.intersection(SEARCH_INTENT_TERMS))
        recovery_hits = sorted(tokens.intersection(RECOVERY_INTENT_TERMS))

        if recovery_hits:
            intent = "recovery_proposal"
        elif write_hits:
            intent = "mutation_proposal"
        elif verify_hits:
            intent = "verification"
        elif search_hits:
            intent = "research"
        else:
            intent = "analysis"

        return {
            "intent": intent,
            "write_terms": write_hits,
            "verify_terms": verify_hits,
            "search_terms": search_hits,
            "recovery_terms": recovery_hits,
            "authorization": False,
        }

    def plan(
        self,
        goal: str,
        *,
        evidence_limit: int = 5,
    ) -> Dict[str, Any]:
        """Construct a deterministic read-only execution plan."""
        clean_goal = goal.strip()

        if not clean_goal:
            raise ValueError("goal cannot be empty.")

        intent = self.classify_intent(clean_goal)
        generalization = self.generalizer.process(
            clean_goal,
            source="agent_runtime",
            thread_id=self.thread_id,
            tags=("agent", "proposal", "read_only"),
        )

        evidence = self.query_spines(
            clean_goal,
            limit=evidence_limit,
        )

        steps: List[Dict[str, Any]] = [
            {
                "order": 1,
                "action": "verify_chain",
                "mode": "read_only",
            },
            {
                "order": 2,
                "action": "observe_recent_state",
                "mode": "read_only",
            },
            {
                "order": 3,
                "action": "query_repository_documents",
                "mode": "read_only",
            },
            {
                "order": 4,
                "action": "generalize_goal",
                "mode": "read_only",
            },
        ]

        if intent["intent"] in {
            "mutation_proposal",
            "recovery_proposal",
        }:
            steps.append(
                {
                    "order": 5,
                    "action": "prepare_human_review_packet",
                    "mode": "proposal_only",
                }
            )
        else:
            steps.append(
                {
                    "order": 5,
                    "action": "return_analysis",
                    "mode": "read_only",
                }
            )

        packet = {
            "type": "holo_agent_plan",
            "version": AGENT_VERSION,
            "goal": clean_goal,
            "thread_id": self.thread_id,
            "intent": intent,
            "steps": steps,
            "generalization": generalization,
            "evidence": evidence,
            "write_authorized": False,
            "timestamp": utc_now(),
        }

        packet["plan_hash"] = stable_hash(
            {
                key: value
                for key, value in packet.items()
                if key not in {"timestamp", "plan_hash"}
            }
        )

        return packet

    def propose(
        self,
        goal: str,
        *,
        evidence_limit: int = 5,
    ) -> Dict[str, Any]:
        """Produce a reviewable proposal without executing it."""
        plan = self.plan(
            goal,
            evidence_limit=evidence_limit,
        )
        observation = self.observe(last=5)

        intent_name = plan["intent"]["intent"]

        if intent_name == "verification":
            proposed_action = {
                "action": "report_verification",
                "target": "canonical_chain",
                "requires_commit": False,
            }

        elif intent_name == "research":
            proposed_action = {
                "action": "report_research",
                "target": "repository_documents",
                "requires_commit": False,
            }

        elif intent_name == "recovery_proposal":
            proposed_action = {
                "action": "request_recovery_review",
                "target": "rebirth_boundary",
                "requires_commit": True,
                "execution_available": False,
            }

        elif intent_name == "mutation_proposal":
            proposed_action = {
                "action": "request_delta_review",
                "target": "canonical_chain",
                "requires_commit": True,
                "execution_available": False,
            }

        else:
            proposed_action = {
                "action": "report_analysis",
                "target": "operator",
                "requires_commit": False,
            }

        proposal: Dict[str, Any] = {
            "type": PROPOSAL_TYPE,
            "version": PROPOSAL_VERSION,
            "status": "review_pending",
            "goal": goal.strip(),
            "thread_id": self.thread_id,
            "agent": self.identity(),
            "proposed_action": proposed_action,
            "plan": plan,
            "observation": observation,
            "approval": {
                "required": bool(
                    proposed_action["requires_commit"]
                ),
                "approved": False,
                "reviewer": None,
                "approved_at": None,
            },
            "execution": {
                "performed": False,
                "available_in_runtime": False,
                "reason": (
                    "This runtime is structurally read-only. "
                    "Use a separate reviewed commit boundary."
                ),
            },
            "timestamp": utc_now(),
        }

        hashable = {
            key: value
            for key, value in proposal.items()
            if key not in {"timestamp", "proposal_hash"}
        }
        proposal["proposal_hash"] = stable_hash(hashable)

        return proposal

    def execute(self, *_: Any, **__: Any) -> None:
        """Reject execution attempts by construction."""
        raise ReadOnlyViolation(
            "HoloAgentRuntime is read-only and cannot execute proposals."
        )

    def append(self, *_: Any, **__: Any) -> None:
        """Reject direct append attempts by construction."""
        raise ReadOnlyViolation(
            "Direct chain append is not available in HoloAgentRuntime."
        )

    def rebirth(self, *_: Any, **__: Any) -> None:
        """Reject rebirth attempts by construction."""
        raise ReadOnlyViolation(
            "Rebirth is outside the read-only agent boundary."
        )


def get_agent_runtime(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    *,
    repo_root: str | Path = REPO_ROOT,
    thread_id: Optional[str] = None,
) -> HoloAgentRuntime:
    """Create a read-only Holo/Sim agent runtime."""
    return HoloAgentRuntime(
        chain_path,
        repo_root=repo_root,
        thread_id=thread_id,
    )


def write_output(
    result: Mapping[str, Any],
    output: Optional[str],
) -> None:
    """Print a result and optionally export the review artifact."""
    rendered = json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    if output:
        Path(output).write_text(
            rendered + "\n",
            encoding="utf-8",
        )

    print(rendered)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only Holo/Sim agent proposal runtime."
    )
    parser.add_argument(
        "--file",
        "-f",
        default=str(DEFAULT_CHAIN_FILE),
        help="Canonical HoloChain JSONL path",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Repository root used for spine discovery",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Optional continuity thread reference",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "identity",
        help="Show runtime identity and enforced boundaries",
    )

    observe_parser = subparsers.add_parser(
        "observe",
        help="Observe verified recent chain state",
    )
    observe_parser.add_argument(
        "--last",
        type=int,
        default=5,
    )

    subparsers.add_parser(
        "verify",
        help="Verify canonical persistence",
    )

    query_parser = subparsers.add_parser(
        "query",
        help="Search repository spine documents",
    )
    query_parser.add_argument("query")
    query_parser.add_argument(
        "--limit",
        type=int,
        default=5,
    )

    plan_parser = subparsers.add_parser(
        "plan",
        help="Build a read-only plan",
    )
    plan_parser.add_argument("goal")
    plan_parser.add_argument(
        "--limit",
        type=int,
        default=5,
    )
    plan_parser.add_argument(
        "--output",
        default=None,
    )

    propose_parser = subparsers.add_parser(
        "propose",
        help="Build a human-review proposal",
    )
    propose_parser.add_argument("goal")
    propose_parser.add_argument(
        "--limit",
        type=int,
        default=5,
    )
    propose_parser.add_argument(
        "--output",
        default=None,
        help="Optional proposal JSON output file",
    )

    args = parser.parse_args()

    runtime = get_agent_runtime(
        args.file,
        repo_root=args.repo_root,
        thread_id=args.thread_id,
    )

    output: Optional[str] = None

    if args.command == "identity":
        result = runtime.identity()

    elif args.command == "observe":
        result = runtime.observe(last=args.last)

    elif args.command == "verify":
        result = runtime.verify()

    elif args.command == "query":
        result = runtime.query_spines(
            args.query,
            limit=args.limit,
        )

    elif args.command == "plan":
        result = runtime.plan(
            args.goal,
            evidence_limit=args.limit,
        )
        output = args.output

    elif args.command == "propose":
        result = runtime.propose(
            args.goal,
            evidence_limit=args.limit,
        )
        output = args.output

    else:
        raise SystemExit(f"Unknown command: {args.command}")

    write_output(result, output)


if __name__ == "__main__":
    main()