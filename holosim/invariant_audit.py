from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from holosim.replay_verifier import ReceiptState, replay_receipt
    from holosim.transition_receipt import (
        git_snapshot,
        load_receipt,
        verify_holo_chain,
        verify_merkle_store,
        verify_receipt,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.replay_verifier import ReceiptState, replay_receipt
    from holosim.transition_receipt import (
        git_snapshot,
        load_receipt,
        verify_holo_chain,
        verify_merkle_store,
        verify_receipt,
    )


AUDIT_TYPE = "holo_invariant_audit"
AUDIT_VERSION = 2
DEFAULT_RECEIPT_DIR = Path("runtime_watch") / "receipts"


class InvariantAuditError(RuntimeError):
    """Raised when the repository audit cannot be completed."""


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


def _discover_receipts(receipt_dir: Path) -> list[Path]:
    if not receipt_dir.exists():
        return []

    return sorted(
        path
        for path in receipt_dir.rglob("*.json")
        if path.is_file()
    )


def _classify_without_replay(
    *,
    receipt: Mapping[str, Any],
    integrity_valid: bool,
    commit_exists: bool,
) -> ReceiptState:
    if not integrity_valid:
        return ReceiptState.CORRUPTED
    if not commit_exists:
        return ReceiptState.MISSING_COMMIT
    if receipt.get("verification_passed") is not True:
        return ReceiptState.FAILED_AT_CREATION
    return ReceiptState.HISTORICAL


def _audit_receipt(
    receipt_path: Path,
    *,
    repo_root: Path,
    replay: bool,
    timeout: int,
    require_clean: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(receipt_path),
        "loadable": False,
        "integrity_valid": False,
        "recorded_verification_passed": False,
        "commit_exists": False,
        "replay_attempted": replay,
        "replay_valid": None,
        "receipt_state": ReceiptState.CORRUPTED.value,
        "errors": [],
    }

    try:
        receipt = load_receipt(receipt_path)
        result["loadable"] = True
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        return result

    try:
        integrity = verify_receipt(
            receipt,
            repo_root=None,
            require_current_commit=False,
        )
        result["integrity"] = integrity
        result["integrity_valid"] = bool(integrity.get("valid"))
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")

    result["recorded_verification_passed"] = (
        receipt.get("verification_passed") is True
    )

    recorded_git = receipt.get("git_after")
    recorded_commit = (
        recorded_git.get("commit")
        if isinstance(recorded_git, Mapping)
        else None
    )
    result["recorded_commit"] = recorded_commit
    result["commit_exists"] = _git_commit_exists(
        repo_root,
        recorded_commit,
    )

    if replay:
        try:
            replay_report = replay_receipt(
                receipt_path,
                repo_root=repo_root,
                timeout=timeout,
                require_clean=require_clean,
            )
            result["replay"] = replay_report
            result["replay_valid"] = bool(replay_report.get("valid"))
            result["receipt_state"] = replay_report["receipt_state"]
        except Exception as exc:
            result["replay_valid"] = False
            result["receipt_state"] = ReceiptState.UNREPRODUCIBLE.value
            result["errors"].append(f"{type(exc).__name__}: {exc}")
    else:
        result["receipt_state"] = _classify_without_replay(
            receipt=receipt,
            integrity_valid=result["integrity_valid"],
            commit_exists=result["commit_exists"],
        ).value

    result["valid_evidence"] = result["receipt_state"] in {
        ReceiptState.CURRENT.value,
        ReceiptState.HISTORICAL.value,
        ReceiptState.FAILED_AT_CREATION.value,
    }
    result["corrupted"] = result["receipt_state"] == ReceiptState.CORRUPTED.value
    result["missing"] = result["receipt_state"] == ReceiptState.MISSING_COMMIT.value
    result["unreproducible"] = (
        result["receipt_state"] == ReceiptState.UNREPRODUCIBLE.value
    )

    return result


def _receipt_summary(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item["receipt_state"]) for item in items)

    return {
        "total": len(items),
        "current": counts[ReceiptState.CURRENT.value],
        "historical": counts[ReceiptState.HISTORICAL.value],
        "failed_at_creation": counts[ReceiptState.FAILED_AT_CREATION.value],
        "corrupted": counts[ReceiptState.CORRUPTED.value],
        "missing_commit": counts[ReceiptState.MISSING_COMMIT.value],
        "unreproducible": counts[ReceiptState.UNREPRODUCIBLE.value],
    }


def audit_repository(
    *,
    repo_root: Path,
    receipt_dir: Path,
    chain_path: Path,
    merkle_path: Path,
    replay: bool = True,
    timeout: int = 300,
    require_clean: bool = False,
) -> dict[str, Any]:
    """
    Audit current integrity and historical receipt lineage separately.

    A dirty working tree is reported as repository state, not corruption.
    A receipt that failed at creation remains valid historical evidence.
    """
    repo_root = repo_root.resolve()
    receipt_dir = (
        receipt_dir
        if receipt_dir.is_absolute()
        else repo_root / receipt_dir
    )

    git_state = git_snapshot(repo_root)
    receipts = [
        _audit_receipt(
            path,
            repo_root=repo_root,
            replay=replay,
            timeout=timeout,
            require_clean=require_clean,
        )
        for path in _discover_receipts(receipt_dir)
    ]
    receipt_summary = _receipt_summary(receipts)

    chain = verify_holo_chain(repo_root, chain_path)
    merkle = verify_merkle_store(repo_root, merkle_path)

    git_integrity_valid = bool(git_state.get("commit"))
    git_clean = bool(git_state.get("repository_clean"))

    receipts_integrity_valid = (
        receipt_summary["corrupted"] == 0
        and receipt_summary["missing_commit"] == 0
    )
    replay_integrity_valid = (
        receipt_summary["unreproducible"] == 0
        if replay
        else True
    )
    chain_valid = chain.get("verified") is not False
    merkle_valid = merkle.get("verified") is not False

    core_checks = {
        "git_integrity": git_integrity_valid,
        "receipt_integrity": receipts_integrity_valid,
        "replay_integrity": replay_integrity_valid,
        "holo_chain": chain_valid,
        "merkle": merkle_valid,
    }

    passed = sum(1 for value in core_checks.values() if value)
    total = len(core_checks)
    integrity_percent = round((passed / total) * 100, 2) if total else 0.0

    valid = all(core_checks.values())
    operational_status = (
        "clean"
        if git_clean
        else "dirty"
    )

    if require_clean and not git_clean:
        valid = False

    return {
        "type": AUDIT_TYPE,
        "version": AUDIT_VERSION,
        "valid": valid,
        "status": "PASS" if valid else "FAIL",
        "integrity_percent": integrity_percent,
        "operational_status": operational_status,
        "checks": {
            "git": {
                "integrity_valid": git_integrity_valid,
                "repository_clean": git_clean,
                "require_clean": require_clean,
                "details": git_state,
            },
            "receipts": {
                "integrity_valid": receipts_integrity_valid,
                "summary": receipt_summary,
                "items": receipts,
            },
            "replay": {
                "integrity_valid": replay_integrity_valid,
                "enabled": replay,
            },
            "holo_chain": {
                "valid": chain_valid,
                "details": chain,
            },
            "merkle": {
                "valid": merkle_valid,
                "details": merkle,
            },
        },
    }


def _print_summary(report: Mapping[str, Any]) -> None:
    checks = report["checks"]
    summary = checks["receipts"]["summary"]

    print("HOLO AUDIT v2")
    print()
    print(
        f"Git integrity.... "
        f"{'PASS' if checks['git']['integrity_valid'] else 'FAIL'}"
    )
    print(
        f"Working tree..... "
        f"{'CLEAN' if checks['git']['repository_clean'] else 'DIRTY'}"
    )
    print(
        f"Receipt integrity "
        f"{'PASS' if checks['receipts']['integrity_valid'] else 'FAIL'}"
    )
    print(f"  current........ {summary['current']}")
    print(f"  historical..... {summary['historical']}")
    print(f"  failed-created. {summary['failed_at_creation']}")
    print(f"  corrupted...... {summary['corrupted']}")
    print(f"  missing-commit. {summary['missing_commit']}")
    print(f"  unreproducible. {summary['unreproducible']}")
    print(
        f"Replay integrity. "
        f"{'PASS' if checks['replay']['integrity_valid'] else 'FAIL'}"
    )
    print(
        f"HoloChain........ "
        f"{'PASS' if checks['holo_chain']['valid'] else 'FAIL'}"
    )
    print(
        f"Merkle........... "
        f"{'PASS' if checks['merkle']['valid'] else 'FAIL'}"
    )
    print()
    print(f"Overall Integrity: {report['integrity_percent']:.2f}%")
    print(f"Operational State: {report['operational_status'].upper()}")
    print(f"Status: {report['status']}")


def run_self_test() -> None:
    sample = [
        {"receipt_state": ReceiptState.CURRENT.value},
        {"receipt_state": ReceiptState.HISTORICAL.value},
        {"receipt_state": ReceiptState.FAILED_AT_CREATION.value},
        {"receipt_state": ReceiptState.CORRUPTED.value},
    ]

    summary = _receipt_summary(sample)
    assert summary["total"] == 4
    assert summary["current"] == 1
    assert summary["historical"] == 1
    assert summary["failed_at_creation"] == 1
    assert summary["corrupted"] == 1

    with tempfile.TemporaryDirectory() as temp_dir:
        receipt_dir = Path(temp_dir)
        (receipt_dir / "a.json").write_text("{}", encoding="utf-8")
        (receipt_dir / "b.txt").write_text("ignored", encoding="utf-8")
        discovered = _discover_receipts(receipt_dir)
        assert len(discovered) == 1

    print("✅ Invariant audit v2 self-test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Holo/Sim current integrity and historical lineage."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--receipt-dir",
        default=str(DEFAULT_RECEIPT_DIR),
    )
    parser.add_argument(
        "--chain-file",
        default="holo_memory.jsonl",
    )
    parser.add_argument(
        "--merkle-file",
        default="holo_merkle.jsonl",
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--skip-replay", action="store_true")
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Fail the audit when the current working tree is dirty",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")

    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    report = audit_repository(
        repo_root=Path(args.repo_root),
        receipt_dir=Path(args.receipt_dir),
        chain_path=Path(args.chain_file),
        merkle_path=Path(args.merkle_file),
        replay=not args.skip_replay,
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


if __name__ == "__main__":
    main()
