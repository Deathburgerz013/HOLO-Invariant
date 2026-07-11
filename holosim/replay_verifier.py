from __future__ import annotations

import argparse
import json
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from holosim.transition_receipt import (
        git_snapshot,
        load_receipt,
        run_command,
        verify_holo_chain,
        verify_merkle_store,
        verify_receipt,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.transition_receipt import (
        git_snapshot,
        load_receipt,
        run_command,
        verify_holo_chain,
        verify_merkle_store,
        verify_receipt,
    )


REPORT_TYPE = "holo_transition_replay_report"
REPORT_VERSION = 2


class ReceiptState(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    FAILED_AT_CREATION = "failed_at_creation"
    CORRUPTED = "corrupted"
    MISSING_COMMIT = "missing_commit"
    UNREPRODUCIBLE = "unreproducible"


class ReplayVerificationError(RuntimeError):
    """Raised when replay verification cannot be completed."""


def _git_commit_exists(repo_root: Path, commit: str | None) -> bool:
    if not commit:
        return False

    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode == 0


def _is_ancestor(repo_root: Path, older: str | None, newer: str | None) -> bool:
    if not older or not newer:
        return False

    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode == 0


def _recorded_path(
    receipt: Mapping[str, Any],
    section: str,
    default: str,
) -> Path:
    persistence = receipt.get("persistence")
    if not isinstance(persistence, Mapping):
        return Path(default)

    record = persistence.get(section)
    if not isinstance(record, Mapping):
        return Path(default)

    value = record.get("path")
    if not isinstance(value, str) or not value.strip():
        return Path(default)

    return Path(value)


def _compare_test(
    recorded: Mapping[str, Any] | None,
    replayed: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Compare stable test behavior.

    Output hashes are retained for evidence, but they do not have to match.
    Test output can vary slightly across Python and pytest versions while the
    actual invariant remains: same command, same return state, still passing.
    """
    recorded = recorded or {}

    command_matches = recorded.get("command") == replayed.get("command")
    return_code_matches = (
        recorded.get("return_code") == replayed.get("return_code")
    )
    pass_state_matches = recorded.get("passed") == replayed.get("passed")

    valid = (
        command_matches
        and return_code_matches
        and pass_state_matches
        and replayed.get("passed") is True
    )

    return {
        "valid": valid,
        "command_matches": command_matches,
        "return_code_matches": return_code_matches,
        "pass_state_matches": pass_state_matches,
        "recorded": {
            "command": recorded.get("command"),
            "return_code": recorded.get("return_code"),
            "passed": recorded.get("passed"),
            "stdout_hash": recorded.get("stdout_hash"),
            "stderr_hash": recorded.get("stderr_hash"),
        },
        "replayed": {
            "command": replayed.get("command"),
            "return_code": replayed.get("return_code"),
            "passed": replayed.get("passed"),
            "stdout_hash": replayed.get("stdout_hash"),
            "stderr_hash": replayed.get("stderr_hash"),
        },
    }


def _compare_persistence(
    recorded: Mapping[str, Any] | None,
    replayed: Mapping[str, Any],
    root_field: str,
) -> dict[str, Any]:
    """
    Compare persistence state exactly when the receipt recorded a valid state.

    A receipt that failed at creation is historical evidence, not a successful
    baseline. In that case the replay is classified rather than forced to pass.
    """
    recorded = recorded or {}

    exists_matches = recorded.get("exists") == replayed.get("exists")
    verification_matches = (
        recorded.get("verified") == replayed.get("verified")
    )
    entries_match = recorded.get("entries") == replayed.get("entries")
    root_matches = recorded.get(root_field) == replayed.get(root_field)
    file_hash_matches = (
        recorded.get("file_hash") == replayed.get("file_hash")
    )

    recorded_was_valid = recorded.get("verified") is True

    valid = (
        recorded_was_valid
        and exists_matches
        and verification_matches
        and entries_match
        and root_matches
        and file_hash_matches
        and replayed.get("verified") is True
    )

    return {
        "valid": valid,
        "recorded_was_valid": recorded_was_valid,
        "exists_matches": exists_matches,
        "verification_matches": verification_matches,
        "entries_match": entries_match,
        "root_matches": root_matches,
        "file_hash_matches": file_hash_matches,
        "recorded": dict(recorded),
        "replayed": dict(replayed),
    }


def classify_receipt_state(
    *,
    integrity_valid: bool,
    recorded_verification_passed: bool,
    commit_exists: bool,
    commit_is_current: bool,
    commit_is_ancestor: bool,
    reproduction_valid: bool,
) -> ReceiptState:
    if not integrity_valid:
        return ReceiptState.CORRUPTED
    if not commit_exists:
        return ReceiptState.MISSING_COMMIT
    if not recorded_verification_passed:
        return ReceiptState.FAILED_AT_CREATION
    if not reproduction_valid:
        return ReceiptState.UNREPRODUCIBLE
    if commit_is_current:
        return ReceiptState.CURRENT
    if commit_is_ancestor:
        return ReceiptState.HISTORICAL
    return ReceiptState.HISTORICAL


def replay_receipt(
    receipt_path: Path,
    *,
    repo_root: Path,
    timeout: int = 300,
    require_clean: bool = False,
) -> dict[str, Any]:
    """
    Replay a receipt as historical evidence.

    Current HEAD does not need to equal the receipt commit. The receipt commit
    only needs to exist. When it is an ancestor of HEAD, the receipt is valid
    historical evidence rather than a failure.
    """
    repo_root = repo_root.resolve()
    receipt = load_receipt(receipt_path)

    receipt_integrity = verify_receipt(
        receipt,
        repo_root=None,
        require_current_commit=False,
    )

    current_git = git_snapshot(repo_root)
    recorded_git = receipt.get("git_after")
    if not isinstance(recorded_git, Mapping):
        recorded_git = {}

    recorded_commit = recorded_git.get("commit")
    current_commit = current_git.get("commit")

    commit_exists = _git_commit_exists(repo_root, recorded_commit)
    commit_is_current = bool(
        recorded_commit and current_commit and recorded_commit == current_commit
    )
    commit_is_ancestor = _is_ancestor(
        repo_root,
        recorded_commit,
        current_commit,
    )

    git_checks = {
        "recorded_commit": recorded_commit,
        "current_commit": current_commit,
        "commit_exists": commit_exists,
        "commit_is_current": commit_is_current,
        "commit_is_ancestor_of_head": commit_is_ancestor,
        "repository_clean": bool(current_git.get("repository_clean")),
        "require_clean": require_clean,
    }
    git_valid = commit_exists and (
        git_checks["repository_clean"] if require_clean else True
    )

    recorded_tests = receipt.get("tests")
    if not isinstance(recorded_tests, Mapping):
        raise ReplayVerificationError(
            "Receipt does not contain a valid tests section"
        )

    pytest_replay = run_command(
        [sys.executable, "-m", "pytest", "holosim/tests", "-q"],
        cwd=repo_root,
        timeout=timeout,
    )
    merkle_replay = run_command(
        [
            sys.executable,
            str(repo_root / "holosim" / "merkle_persistence.py"),
            "self-test",
        ],
        cwd=repo_root,
        timeout=timeout,
    )

    test_checks = {
        "pytest": _compare_test(
            recorded_tests.get("pytest")
            if isinstance(recorded_tests.get("pytest"), Mapping)
            else None,
            pytest_replay,
        ),
        "merkle_self_test": _compare_test(
            recorded_tests.get("merkle_self_test")
            if isinstance(recorded_tests.get("merkle_self_test"), Mapping)
            else None,
            merkle_replay,
        ),
    }
    tests_valid = all(item["valid"] for item in test_checks.values())

    persistence_recorded = receipt.get("persistence")
    if not isinstance(persistence_recorded, Mapping):
        raise ReplayVerificationError(
            "Receipt does not contain a valid persistence section"
        )

    chain_path = _recorded_path(
        receipt,
        "holo_chain",
        "holo_memory.jsonl",
    )
    merkle_path = _recorded_path(
        receipt,
        "merkle_store",
        "holo_merkle.jsonl",
    )

    chain_replay = verify_holo_chain(repo_root, chain_path)
    merkle_replay_state = verify_merkle_store(repo_root, merkle_path)

    persistence_checks = {
        "holo_chain": _compare_persistence(
            persistence_recorded.get("holo_chain")
            if isinstance(
                persistence_recorded.get("holo_chain"),
                Mapping,
            )
            else None,
            chain_replay,
            "latest_hash",
        ),
        "merkle_store": _compare_persistence(
            persistence_recorded.get("merkle_store")
            if isinstance(
                persistence_recorded.get("merkle_store"),
                Mapping,
            )
            else None,
            merkle_replay_state,
            "merkle_root",
        ),
    }

    recorded_verification_passed = (
        receipt.get("verification_passed") is True
    )

    if recorded_verification_passed:
        persistence_valid = all(
            item["valid"]
            for item in persistence_checks.values()
            if item["recorded"].get("exists") is True
        )
    else:
        persistence_valid = False

    reproduction_valid = (
        receipt_integrity["valid"]
        and git_valid
        and tests_valid
        and persistence_valid
        and recorded_verification_passed
    )

    state = classify_receipt_state(
        integrity_valid=receipt_integrity["valid"],
        recorded_verification_passed=recorded_verification_passed,
        commit_exists=commit_exists,
        commit_is_current=commit_is_current,
        commit_is_ancestor=commit_is_ancestor,
        reproduction_valid=reproduction_valid,
    )

    valid = state in {
        ReceiptState.CURRENT,
        ReceiptState.HISTORICAL,
    }

    return {
        "type": REPORT_TYPE,
        "version": REPORT_VERSION,
        "valid": valid,
        "status": "PASS" if valid else "FAIL",
        "receipt_state": state.value,
        "receipt": {
            "path": str(receipt_path.resolve()),
            "receipt_hash": receipt.get("receipt_hash"),
            "integrity": receipt_integrity,
            "verification_passed": recorded_verification_passed,
        },
        "git": {
            "valid": git_valid,
            "checks": git_checks,
            "recorded": dict(recorded_git),
            "current": current_git,
        },
        "tests": {
            "valid": tests_valid,
            "checks": test_checks,
        },
        "persistence": {
            "valid": persistence_valid,
            "checks": persistence_checks,
        },
    }


def _print_summary(report: Mapping[str, Any]) -> None:
    print(report["status"])
    print(f"Receipt state: {report['receipt_state']}")
    print(
        f"Receipt hash: "
        f"{'PASS' if report['receipt']['integrity']['hash_valid'] else 'FAIL'}"
    )
    print(
        f"Recorded commit exists: "
        f"{'PASS' if report['git']['checks']['commit_exists'] else 'FAIL'}"
    )
    print(
        f"Historical lineage: "
        f"{'PASS' if report['git']['checks']['commit_is_ancestor_of_head'] or report['git']['checks']['commit_is_current'] else 'FAIL'}"
    )
    print(
        f"Pytest replay: "
        f"{'PASS' if report['tests']['checks']['pytest']['valid'] else 'FAIL'}"
    )
    print(
        f"Merkle self-test replay: "
        f"{'PASS' if report['tests']['checks']['merkle_self_test']['valid'] else 'FAIL'}"
    )
    print(
        f"HoloChain state: "
        f"{'PASS' if report['persistence']['checks']['holo_chain']['valid'] else 'FAIL'}"
    )
    print(
        f"Merkle store state: "
        f"{'PASS' if report['persistence']['checks']['merkle_store']['valid'] else 'FAIL'}"
    )


def run_self_test() -> None:
    assert classify_receipt_state(
        integrity_valid=True,
        recorded_verification_passed=True,
        commit_exists=True,
        commit_is_current=True,
        commit_is_ancestor=True,
        reproduction_valid=True,
    ) == ReceiptState.CURRENT

    assert classify_receipt_state(
        integrity_valid=True,
        recorded_verification_passed=True,
        commit_exists=True,
        commit_is_current=False,
        commit_is_ancestor=True,
        reproduction_valid=True,
    ) == ReceiptState.HISTORICAL

    assert classify_receipt_state(
        integrity_valid=True,
        recorded_verification_passed=False,
        commit_exists=True,
        commit_is_current=False,
        commit_is_ancestor=True,
        reproduction_valid=False,
    ) == ReceiptState.FAILED_AT_CREATION

    assert classify_receipt_state(
        integrity_valid=False,
        recorded_verification_passed=True,
        commit_exists=True,
        commit_is_current=False,
        commit_is_ancestor=True,
        reproduction_valid=False,
    ) == ReceiptState.CORRUPTED

    print("✅ Replay verifier v2 self-test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay Holo/Sim transition receipts as historical evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay one transition receipt",
    )
    replay_parser.add_argument("receipt")
    replay_parser.add_argument("--repo-root", default=".")
    replay_parser.add_argument("--timeout", type=int, default=300)
    replay_parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Fail replay if the current repository is dirty",
    )
    replay_parser.add_argument("--json", action="store_true")

    subparsers.add_parser(
        "self-test",
        help="Run isolated receipt-state tests",
    )

    args = parser.parse_args()

    if args.command == "replay":
        report = replay_receipt(
            Path(args.receipt),
            repo_root=Path(args.repo_root),
            timeout=args.timeout,
            require_clean=args.require_clean,
        )

        if args.json:
            print(
                json.dumps(
                    report,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            _print_summary(report)

        if not report["valid"]:
            raise SystemExit(1)

    elif args.command == "self-test":
        run_self_test()

    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
