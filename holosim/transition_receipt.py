from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

RECEIPT_TYPE = "holo_verified_transition_receipt"
RECEIPT_VERSION = 1
DEFAULT_OUTPUT_DIR = Path("runtime_watch") / "receipts"


class ReceiptError(RuntimeError):
    """Base error for transition receipt failures."""


class ReceiptVerificationError(ReceiptError):
    """Raised when a receipt fails integrity verification."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(command: Sequence[str], *, cwd: Path, timeout: int = 300) -> dict[str, Any]:
    started_at = utc_now()
    try:
        completed = subprocess.run(
            list(command), cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
        return_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        return_code = None
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        timed_out = True

    evidence = {
        "command": list(command),
        "started_at": started_at,
        "finished_at": utc_now(),
        "return_code": return_code,
        "timed_out": timed_out,
        "passed": return_code == 0 and not timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_hash": hash_bytes(stdout.encode("utf-8")),
        "stderr_hash": hash_bytes(stderr.encode("utf-8")),
    }
    evidence["result_hash"] = stable_hash(evidence)
    return evidence


def git_text(repo_root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=repo_root, text=True,
            encoding="utf-8", errors="replace", stderr=subprocess.DEVNULL,
        ).strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def git_snapshot(repo_root: Path) -> dict[str, Any]:
    status = git_text(repo_root, "status", "--porcelain")
    return {
        "branch": git_text(repo_root, "branch", "--show-current"),
        "commit": git_text(repo_root, "rev-parse", "HEAD"),
        "parent_commit": git_text(repo_root, "rev-parse", "HEAD^"),
        "origin_main": git_text(repo_root, "rev-parse", "origin/main"),
        "repository_clean": not bool(status),
        "status_porcelain": status or "",
    }


def verify_holo_chain(repo_root: Path, chain_path: Path) -> dict[str, Any]:
    absolute = chain_path if chain_path.is_absolute() else repo_root / chain_path
    result = {
        "path": str(absolute), "exists": absolute.exists(), "file_hash": hash_file(absolute),
        "verified": None, "entries": None, "latest_hash": None, "error": None,
    }
    if not absolute.exists():
        return result
    try:
        from holosim.core import HoloChain
        entries = HoloChain(absolute).load_and_verify()
        result.update({"verified": True, "entries": len(entries), "latest_hash": entries[-1]["hash"] if entries else None})
    except Exception as exc:
        result.update({"verified": False, "error": f"{type(exc).__name__}: {exc}"})
    return result


def verify_merkle_store(repo_root: Path, merkle_path: Path) -> dict[str, Any]:
    absolute = merkle_path if merkle_path.is_absolute() else repo_root / merkle_path
    result = {
        "path": str(absolute), "exists": absolute.exists(), "file_hash": hash_file(absolute),
        "verified": None, "entries": None, "merkle_root": None, "error": None,
    }
    if not absolute.exists():
        return result
    try:
        from holosim.merkle_persistence import MerkleStore
        verification = MerkleStore(absolute).verify()
        result.update({"verified": bool(verification.get("valid")), "entries": verification.get("entries"), "merkle_root": verification.get("merkle_root")})
    except Exception as exc:
        result.update({"verified": False, "error": f"{type(exc).__name__}: {exc}"})
    return result


def compute_receipt_hash(receipt: Mapping[str, Any]) -> str:
    return stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(rendered)
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def create_receipt(*, repo_root: Path, output_dir: Path, reviewer: str,
                   approval_reference: str | None, proposal_hash: str | None,
                   observation_hash: str | None, chain_path: Path,
                   merkle_path: Path, timeout: int) -> tuple[dict[str, Any], Path]:
    repo_root = repo_root.resolve()
    git_before = git_snapshot(repo_root)
    tests = {
        "pytest": run_command([sys.executable, "-m", "pytest", "holosim/tests", "-q"], cwd=repo_root, timeout=timeout),
        "merkle_self_test": run_command([sys.executable, str(repo_root / "holosim" / "merkle_persistence.py"), "self-test"], cwd=repo_root, timeout=timeout),
    }
    chain = verify_holo_chain(repo_root, chain_path)
    merkle = verify_merkle_store(repo_root, merkle_path)
    git_after = git_snapshot(repo_root)
    verification_passed = (
        all(test["passed"] for test in tests.values())
        and git_before["commit"] == git_after["commit"]
        and git_before["repository_clean"] == git_after["repository_clean"]
        and chain["verified"] is not False
        and merkle["verified"] is not False
    )
    receipt: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "created_at": utc_now(),
        "verification_passed": verification_passed,
        "authority": {
            "reviewer": reviewer,
            "approval_reference": approval_reference,
            "approved": bool(reviewer.strip()),
        },
        "lineage": {
            "observation_hash": observation_hash,
            "proposal_hash": proposal_hash,
        },
        "git_before": git_before,
        "git_after": git_after,
        "tests": tests,
        "persistence": {"holo_chain": chain, "merkle_store": merkle},
    }
    receipt["receipt_hash"] = compute_receipt_hash(receipt)
    commit = git_after.get("commit") or "unknown"
    timestamp = receipt["created_at"].replace(":", "").replace("-", "")
    filename = f"transition_{commit[:12]}_{timestamp}.json"
    base = output_dir if output_dir.is_absolute() else repo_root / output_dir
    receipt_path = base / filename
    atomic_write_json(receipt_path, receipt)
    return receipt, receipt_path


def load_receipt(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptVerificationError(f"Could not read receipt: {exc}") from exc
    if not isinstance(value, dict):
        raise ReceiptVerificationError("Receipt must contain a JSON object")
    return value


def verify_receipt(receipt: Mapping[str, Any], *, repo_root: Path | None = None,
                   require_current_commit: bool = False) -> dict[str, Any]:
    expected = compute_receipt_hash(receipt)
    stored = receipt.get("receipt_hash")
    hash_valid = isinstance(stored, str) and stored == expected
    type_valid = receipt.get("type") == RECEIPT_TYPE
    version_valid = receipt.get("version") == RECEIPT_VERSION
    current_commit = None
    commit_matches = None
    if repo_root is not None:
        current_commit = git_snapshot(repo_root.resolve()).get("commit")
        recorded = receipt.get("git_after", {}).get("commit") if isinstance(receipt.get("git_after"), dict) else None
        commit_matches = current_commit == recorded
    valid = hash_valid and type_valid and version_valid
    if require_current_commit:
        valid = valid and commit_matches is True
    return {
        "valid": valid,
        "hash_valid": hash_valid,
        "type_valid": type_valid,
        "version_valid": version_valid,
        "verification_passed": receipt.get("verification_passed"),
        "stored_receipt_hash": stored,
        "computed_receipt_hash": expected,
        "current_commit": current_commit,
        "commit_matches": commit_matches,
    }


def run_self_test() -> None:
    sample: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "created_at": "2026-01-01T00:00:00Z",
        "verification_passed": True,
        "authority": {"reviewer": "self-test", "approval_reference": "test", "approved": True},
        "lineage": {"observation_hash": "a" * 64, "proposal_hash": "b" * 64},
        "git_before": {"commit": "c" * 40},
        "git_after": {"commit": "c" * 40},
        "tests": {},
        "persistence": {},
    }
    sample["receipt_hash"] = compute_receipt_hash(sample)
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "receipt.json"
        atomic_write_json(path, sample)
        loaded = load_receipt(path)
        assert verify_receipt(loaded)["valid"] is True
        loaded["authority"]["reviewer"] = "tampered"
        assert verify_receipt(loaded)["valid"] is False
    print("✅ Transition receipt self-test passed.")


def print_json(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and verify Holo/Sim transition receipts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Run verification and create a transition receipt")
    create_parser.add_argument("--repo-root", default=".")
    create_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    create_parser.add_argument("--reviewer", required=True)
    create_parser.add_argument("--approval-reference", default=None)
    create_parser.add_argument("--proposal-hash", default=None)
    create_parser.add_argument("--observation-hash", default=None)
    create_parser.add_argument("--chain-file", default="holo_memory.jsonl")
    create_parser.add_argument("--merkle-file", default="holo_merkle.jsonl")
    create_parser.add_argument("--timeout", type=int, default=300)

    verify_parser = subparsers.add_parser("verify", help="Verify a saved transition receipt")
    verify_parser.add_argument("receipt")
    verify_parser.add_argument("--repo-root", default=None)
    verify_parser.add_argument("--require-current-commit", action="store_true")

    subparsers.add_parser("self-test", help="Run an isolated receipt integrity self-test")

    args = parser.parse_args()
    if args.command == "create":
        receipt, path = create_receipt(
            repo_root=Path(args.repo_root), output_dir=Path(args.output_dir), reviewer=args.reviewer,
            approval_reference=args.approval_reference, proposal_hash=args.proposal_hash,
            observation_hash=args.observation_hash, chain_path=Path(args.chain_file),
            merkle_path=Path(args.merkle_file), timeout=args.timeout,
        )
        print(f"Receipt: {path}")
        print_json({
            "verification_passed": receipt["verification_passed"],
            "receipt_hash": receipt["receipt_hash"],
            "git_commit": receipt["git_after"]["commit"],
            "repository_clean": receipt["git_after"]["repository_clean"],
        })
        if not receipt["verification_passed"]:
            raise SystemExit(1)
    elif args.command == "verify":
        result = verify_receipt(
            load_receipt(Path(args.receipt)),
            repo_root=Path(args.repo_root) if args.repo_root else None,
            require_current_commit=args.require_current_commit,
        )
        print_json(result)
        if not result["valid"]:
            raise SystemExit(1)
    elif args.command == "self-test":
        run_self_test()


if __name__ == "__main__":
    main()
