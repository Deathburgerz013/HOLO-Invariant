from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

try:
    from holosim.invariant_audit import audit_repository
    from holosim.replay_verifier import replay_receipt
    from holosim.transition_receipt import (
        atomic_write_json,
        create_receipt,
        git_snapshot,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.invariant_audit import audit_repository
    from holosim.replay_verifier import replay_receipt
    from holosim.transition_receipt import (
        atomic_write_json,
        create_receipt,
        git_snapshot,
    )


MANAGER_TYPE = "holo_transition_manager_report"
MANAGER_VERSION = 1

DEFAULT_RECEIPT_DIR = Path("runtime_watch") / "receipts"
DEFAULT_REPORT_DIR = Path("runtime_watch") / "transitions"


class TransitionManagerError(RuntimeError):
    """Raised when a verified transition cannot be completed."""


def _transition_valid(
    *,
    receipt_valid: bool,
    replay_valid: bool,
    audit_valid: bool,
    repository_clean: bool,
    require_clean: bool,
) -> bool:
    return (
        receipt_valid
        and replay_valid
        and audit_valid
        and (repository_clean if require_clean else True)
    )


def _safe_name(value: str) -> str:
    cleaned = "".join(
        character
        for character in value
        if character.isalnum() or character in {"-", "_"}
    )
    return cleaned or "unknown"


def _report_path(
    *,
    repo_root: Path,
    report_dir: Path,
    commit: str | None,
    receipt_hash: str | None,
) -> Path:
    resolved_dir = (
        report_dir
        if report_dir.is_absolute()
        else repo_root / report_dir
    )

    commit_part = _safe_name((commit or "unknown")[:12])
    hash_part = _safe_name((receipt_hash or "unknown")[:12])

    return resolved_dir / f"transition_{commit_part}_{hash_part}.json"


def run_transition(
    *,
    repo_root: Path,
    reviewer: str,
    approval_reference: str | None,
    proposal_hash: str | None,
    observation_hash: str | None,
    receipt_dir: Path,
    report_dir: Path,
    chain_path: Path,
    merkle_path: Path,
    timeout: int = 300,
    require_clean: bool = True,
) -> tuple[dict[str, Any], Path]:
    """
    Execute the complete verified transition workflow.

    Order:
    1. Capture Git state.
    2. Create a transition receipt, which runs tests and persistence checks.
    3. Replay the new receipt against the current repository.
    4. Run the invariant audit across all receipts and persistence layers.
    5. Seal one transition report.

    The manager does not stage, commit, push, append canonical persistence,
    approve itself, or modify source files.
    """
    repo_root = repo_root.resolve()
    git_before = git_snapshot(repo_root)

    if require_clean and not git_before.get("repository_clean"):
        raise TransitionManagerError(
            "Repository must be clean before a verified transition can run."
        )

    receipt, receipt_path = create_receipt(
        repo_root=repo_root,
        output_dir=receipt_dir,
        reviewer=reviewer,
        approval_reference=approval_reference,
        proposal_hash=proposal_hash,
        observation_hash=observation_hash,
        chain_path=chain_path,
        merkle_path=merkle_path,
        timeout=timeout,
    )

    replay = replay_receipt(
        receipt_path,
        repo_root=repo_root,
        timeout=timeout,
        require_clean=require_clean,
    )

    audit = audit_repository(
        repo_root=repo_root,
        receipt_dir=receipt_dir,
        chain_path=chain_path,
        merkle_path=merkle_path,
        replay=True,
        timeout=timeout,
        require_clean=require_clean,
    )

    git_after = git_snapshot(repo_root)

    repository_unchanged = (
        git_before.get("commit") == git_after.get("commit")
        and git_before.get("status_porcelain")
        == git_after.get("status_porcelain")
    )

    valid = (
        _transition_valid(
            receipt_valid=bool(receipt.get("verification_passed")),
            replay_valid=bool(replay.get("valid")),
            audit_valid=bool(audit.get("valid")),
            repository_clean=bool(git_after.get("repository_clean")),
            require_clean=require_clean,
        )
        and repository_unchanged
    )

    report: dict[str, Any] = {
        "type": MANAGER_TYPE,
        "version": MANAGER_VERSION,
        "valid": valid,
        "status": "VERIFIED" if valid else "ABORTED",
        "reviewer": reviewer,
        "approval_reference": approval_reference,
        "lineage": {
            "proposal_hash": proposal_hash,
            "observation_hash": observation_hash,
        },
        "git_before": git_before,
        "git_after": git_after,
        "repository_unchanged": repository_unchanged,
        "receipt": {
            "path": str(receipt_path),
            "hash": receipt.get("receipt_hash"),
            "verification_passed": receipt.get("verification_passed"),
        },
        "replay": replay,
        "audit": audit,
    }

    report_path = _report_path(
        repo_root=repo_root,
        report_dir=report_dir,
        commit=git_after.get("commit"),
        receipt_hash=receipt.get("receipt_hash"),
    )
    atomic_write_json(report_path, report)

    return report, report_path


def _print_summary(report: Mapping[str, Any], report_path: Path) -> None:
    print(f"Transition: {report['status']}")
    print(
        f"Receipt......... "
        f"{'PASS' if report['receipt']['verification_passed'] else 'FAIL'}"
    )
    print(
        f"Replay.......... "
        f"{'PASS' if report['replay']['valid'] else 'FAIL'}"
    )
    print(
        f"Audit........... "
        f"{'PASS' if report['audit']['valid'] else 'FAIL'}"
    )
    print(
        f"Repository...... "
        f"{'UNCHANGED' if report['repository_unchanged'] else 'CHANGED'}"
    )
    print(f"Report.......... {report_path}")


def run_self_test() -> None:
    assert _transition_valid(
        receipt_valid=True,
        replay_valid=True,
        audit_valid=True,
        repository_clean=True,
        require_clean=True,
    )

    assert not _transition_valid(
        receipt_valid=True,
        replay_valid=False,
        audit_valid=True,
        repository_clean=True,
        require_clean=True,
    )

    assert _transition_valid(
        receipt_valid=True,
        replay_valid=True,
        audit_valid=True,
        repository_clean=False,
        require_clean=False,
    )

    assert not _transition_valid(
        receipt_valid=True,
        replay_valid=True,
        audit_valid=True,
        repository_clean=False,
        require_clean=True,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        path = _report_path(
            repo_root=root,
            report_dir=Path("reports"),
            commit="a" * 40,
            receipt_hash="b" * 64,
        )
        assert path.name == "transition_aaaaaaaaaaaa_bbbbbbbbbbbb.json"

    print("✅ Transition manager self-test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the complete Holo/Sim verified transition workflow."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Create, replay, audit, and seal one verified transition",
    )
    run_parser.add_argument("--repo-root", default=".")
    run_parser.add_argument(
        "--reviewer",
        required=True,
        help="Human reviewer or operator identifier",
    )
    run_parser.add_argument("--approval-reference", default=None)
    run_parser.add_argument("--proposal-hash", default=None)
    run_parser.add_argument("--observation-hash", default=None)
    run_parser.add_argument(
        "--receipt-dir",
        default=str(DEFAULT_RECEIPT_DIR),
    )
    run_parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
    )
    run_parser.add_argument(
        "--chain-file",
        default="holo_memory.jsonl",
    )
    run_parser.add_argument(
        "--merkle-file",
        default="holo_merkle.jsonl",
    )
    run_parser.add_argument("--timeout", type=int, default=300)
    run_parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow the workflow to run with a dirty working tree",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete transition report",
    )

    subparsers.add_parser(
        "self-test",
        help="Run isolated transition-manager tests",
    )

    args = parser.parse_args()

    if args.command == "run":
        try:
            report, report_path = run_transition(
                repo_root=Path(args.repo_root),
                reviewer=args.reviewer,
                approval_reference=args.approval_reference,
                proposal_hash=args.proposal_hash,
                observation_hash=args.observation_hash,
                receipt_dir=Path(args.receipt_dir),
                report_dir=Path(args.report_dir),
                chain_path=Path(args.chain_file),
                merkle_path=Path(args.merkle_file),
                timeout=args.timeout,
                require_clean=not args.allow_dirty,
            )
        except TransitionManagerError as exc:
            print(f"Transition: ABORTED")
            print(str(exc))
            raise SystemExit(1) from exc

        if args.json:
            print(
                json.dumps(
                    report,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            print(f"Report: {report_path}")
        else:
            _print_summary(report, report_path)

        if not report["valid"]:
            raise SystemExit(1)

    elif args.command == "self-test":
        run_self_test()

    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
