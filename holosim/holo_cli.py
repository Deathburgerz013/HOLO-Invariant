#!/usr/bin/env python3
"""Holo/Sim CLI - Tamper-evident continuity + maintenance tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HOLOSIM_VERSION,
        MASTER_INDEX_FILE,
        REQUIRED_COMPONENTS,
        REPO_ROOT,
    )
    from holosim.core import HoloChain
    from holosim.operator import get_operator
    from holosim.service import get_service
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HOLOSIM_VERSION,
        MASTER_INDEX_FILE,
        REQUIRED_COMPONENTS,
        REPO_ROOT,
    )
    from holosim.core import HoloChain
    from holosim.operator import get_operator
    from holosim.service import get_service


SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}
INDEX_SUFFIXES = {".md", ".py", ".jsonl", ".toml", ".yaml", ".yml"}
SPINE_KEYWORDS = ("Spine", "Invariant", "HSSCE", "HOLO", "Master_Index", "Core", "Loop")
HEADER_PATTERN = re.compile(r"█†█ Holo/Sim █†█")


def is_skipped_path(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def get_git_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "branch", "--show-current"],
            text=True,
            stderr=subprocess.DEVNULL,
            cwd=REPO_ROOT,
        ).strip() or "Unknown"
    except Exception:
        return "Unavailable"


def generate_master_index(repo_path: str | Path = REPO_ROOT, output: str | Path = MASTER_INDEX_FILE) -> str:
    """Generate a verified file inventory with SHA-256 hashes."""
    repo_root = Path(repo_path).resolve()
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    header = """|===========================================| |
| | █†█ Holo/Sim █†█ █†█HSSCE█†█ | |===========================================| |
| Document Title | Master_Index_Auto.md | AUTO-GENERATED | ANCHOR: CANYON_BROCK_HANEY |
|===========================================| |

Auto-generated Master Index — Verified via HOLO/Sim Loop
Generated: {timestamp}
Anchor: {anchor}
GitHub: https://github.com/Deathburgerz013/HOLO-Invariant
Active Hash: {active_hash}
Holo/Sim Version: {version}

File Inventory with SHA-256 hashes (for tamper-evidence):

"""

    content = header.format(
        timestamp=datetime.now().isoformat(),
        anchor=ANCHOR,
        active_hash=ACTIVE_HASH,
        version=HOLOSIM_VERSION,
    )

    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if is_skipped_path(path):
            continue
        if path.name.startswith("Master_Index_Auto"):
            continue
        if path.suffix.lower() not in INDEX_SUFFIXES:
            continue

        try:
            hash_val = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            rel_path = path.relative_to(repo_root).as_posix()
            content += f"- [{path.name}]({rel_path}) | Last: {mtime.date()} | Hash: {hash_val}...\n"
        except Exception as e:
            content += f"- {path.name} (read error: {e})\n"

    output_path.write_text(content, encoding="utf-8")
    return content



def has_bound_analysis_frame(path: Path, root: Path) -> bool:
    """Return True when a raw artifact has a valid bound analysis frame."""
    companion = path.with_name(f"{path.stem}_Analysis.md")
    if not companion.is_file():
        return False

    try:
        content = companion.read_text(encoding="utf-8")[:5000]
    except (OSError, UnicodeError):
        return False

    relative_source = path.relative_to(root).as_posix()
    return (
        bool(HEADER_PATTERN.search(content))
        and f"SOURCE_FILE: {relative_source}" in content
        and "SOURCE_ROLE: RAW_EVIDENCE_TRACE" in content
    )


def check_spine_headers(directory: str | Path = REPO_ROOT) -> list[str]:
    """Validate required Holo/Sim header marker in important markdown files."""
    issues: list[str] = []
    root = Path(directory).resolve()

    for path in sorted(root.rglob("*.md")):
        if is_skipped_path(path):
            continue
        if not any(keyword in path.name for keyword in SPINE_KEYWORDS):
            continue

        try:
            content = path.read_text(encoding="utf-8")[:5000]
            if not HEADER_PATTERN.search(content):
                if has_bound_analysis_frame(path, root):
                    continue
                issues.append(f"Missing █†█ Holo/Sim █†█ header in {path.relative_to(root).as_posix()}")
        except Exception as e:
            issues.append(f"Read error {path.as_posix()}: {e}")

    return issues


def run_self_test(chain: HoloChain) -> int:
    """Run core CLI correction-loop checks."""
    print("=== HOLO/SIM SELF TEST ===")

    try:
        health = chain.health()
        print("✅ Health check passed.")
        print(json.dumps(health, indent=2))
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return 1

    try:
        generate_master_index()
        print("✅ Master_Index_Auto.md generated successfully.")
    except Exception as e:
        print(f"❌ Master index generation failed: {e}")
        return 1

    issues = check_spine_headers()
    if issues:
        print("❌ Spine header issues found:")
        for issue in issues:
            print(f"  • {issue}")
        return 1

    print("✅ Spine header check passed.")
    print("✅ Holo/Sim CLI test passed.")
    return 0


def run_doctor(chain: HoloChain) -> int:
    """Inspect the current Holo/Sim installation."""
    print("========== HOLO/SIM DOCTOR ==========\n")

    chain_file = Path(chain.file_path)

    print(f"Holo/Sim Version ........ {HOLOSIM_VERSION}")
    print(f"Core Chain Version ...... {chain.VERSION}")
    print(f"Active Hash ............. {ACTIVE_HASH}")
    print(f"Anchor .................. {ANCHOR}")
    print(f"Python .................. {platform.python_version()}")
    print(f"Platform ................ {platform.system()} {platform.release()}")
    print()

    git_ok = (REPO_ROOT / ".git").exists()
    print(f"Repository .............. {'PASS' if git_ok else 'NOT FOUND'}")
    print(f"Git Branch .............. {get_git_branch()}")
    print(f"Repo Root ............... {REPO_ROOT}")
    print()

    print(f"Chain File .............. {chain_file}")

    try:
        entries = chain.load_and_verify()
        print(f"Entries ................. {len(entries)}")
        print("Integrity ............... PASS")
    except Exception as e:
        print("Entries ................. UNKNOWN")
        print("Integrity ............... FAIL")
        print(f"Error ................... {e}")
        return 1

    print()

    checks = {
        "Master Index": Path("Master_Index.md").exists() or MASTER_INDEX_FILE.exists(),
        **REQUIRED_COMPONENTS,
    }

    failed = False
    for name, target in checks.items():
        passed = bool(target) if isinstance(target, bool) else Path(target).exists()
        print(f"{name:<24} {'PASS' if passed else 'MISSING'}")
        if not passed:
            failed = True

    print()

    spine_issues = check_spine_headers()
    if spine_issues:
        print("Spine Headers ........... FAIL")
        for issue in spine_issues:
            print(f"  • {issue}")
        failed = True
    else:
        print("Spine Headers ........... PASS")

    print()

    if failed:
        print("Recommendation .......... Missing or invalid components detected.")
        return 1

    print("Recommendation .......... System healthy.")
    return 0


def run_operator_summary(chain_path: str | Path) -> int:
    """Print high-level HoloOperator summary."""
    try:
        operator = get_operator(chain_path)
        print(json.dumps(operator.summary(), indent=2))
        return 0
    except Exception as e:
        print(f"❌ Operator summary failed: {e}")
        return 1


def run_service_status(chain_path: str | Path) -> int:
    """Print HoloService runtime status."""
    try:
        service = get_service(chain_path)
        print(json.dumps(service.status(), indent=2))
        return 0
    except Exception as e:
        print(f"❌ Service status failed: {e}")
        return 1


def run_service_verify(chain_path: str | Path) -> int:
    """Verify through HoloService."""
    try:
        service = get_service(chain_path)
        print(json.dumps(service.verify(), indent=2))
        return 0
    except Exception as e:
        print(f"❌ Service verify failed: {e}")
        return 1


def run_replay_command(args: argparse.Namespace) -> int:
    """Run replay views through HoloService."""
    try:
        service = get_service(args.file)

        if args.search:
            result = service.search(args.search, limit=args.limit)
        elif args.timeline:
            result = service.replay_timeline()
        elif args.last is not None:
            result = service.replay.last(args.last)
        else:
            result = service.verify()

        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        print(f"❌ Replay command failed: {e}")
        return 1


def run_service_append(args: argparse.Namespace) -> int:
    """Append content through HoloService."""
    try:
        service = get_service(args.file)
        result = service.append(
            args.text,
            compress=not args.no_compress,
            mirror_to_slots=args.mirror_slots,
            tier=args.tier,
            reviewer=args.reviewer,
            approval_reference=args.approval_reference,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("commit_performed") else 1
    except Exception as e:
        print(f"❌ Service append failed: {e}")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Holo/Sim CLI - Continuity + Maintenance")
    parser.add_argument(
        "--file",
        "-f",
        default=str(DEFAULT_CHAIN_FILE),
        help="Chain file path",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health", help="Show chain health")
    subparsers.add_parser("review", help="Show entries needing review")
    subparsers.add_parser("index", help="Generate Master_Index_Auto.md with hashes + header")
    subparsers.add_parser("check-spines", help="Validate Holo/Sim headers across spines")
    subparsers.add_parser("test", help="Run complete Holo/Sim self-test")
    subparsers.add_parser("doctor", help="Inspect Holo/Sim installation")
    subparsers.add_parser("operator-summary", help="Show HoloOperator summary")
    subparsers.add_parser("service-status", help="Show HoloService status")
    subparsers.add_parser("verify", help="Verify chain through HoloService")

    replay_parser = subparsers.add_parser("replay", help="Replay or inspect verified chain")
    replay_parser.add_argument("--last", type=int, default=None, help="Show latest N entries")
    replay_parser.add_argument("--search", default=None, help="Search chain entries")
    replay_parser.add_argument("--timeline", action="store_true", help="Show compact timeline")
    replay_parser.add_argument("--limit", type=int, default=20, help="Search result limit")

    append_parser = subparsers.add_parser("append", help="Append content through HoloService")
    append_parser.add_argument("text", help="Text/content to append")
    append_parser.add_argument("--no-compress", action="store_true", help="Disable compression")
    append_parser.add_argument("--mirror-slots", action="store_true", help="Mirror append into SlotMerkleDB")
    append_parser.add_argument("--tier", default="standard", help="Slot tier when mirroring")
    append_parser.add_argument("--reviewer", required=True, help="External reviewer identity")
    append_parser.add_argument(
        "--approval-reference",
        required=True,
        help="External approval record reference",
    )

    args = parser.parse_args()
    chain = HoloChain(file_path=args.file)

    if args.command == "health":
        print(json.dumps(chain.health(), indent=2))

    elif args.command == "review":
        suggestions = chain.needs_review()
        if suggestions:
            print(json.dumps(suggestions, indent=2))
        else:
            print("✅ No entries currently need review.")

    elif args.command == "index":
        generate_master_index()
        print("✅ Master_Index_Auto.md generated successfully.")

    elif args.command == "check-spines":
        issues = check_spine_headers()
        if issues:
            print("Issues found:")
            for issue in issues:
                print(f"  • {issue}")
            sys.exit(1)
        print("✅ All checked spines compliant with HOLO/Sim header invariant.")

    elif args.command == "test":
        sys.exit(run_self_test(chain))

    elif args.command == "doctor":
        sys.exit(run_doctor(chain))

    elif args.command == "operator-summary":
        sys.exit(run_operator_summary(args.file))

    elif args.command == "service-status":
        sys.exit(run_service_status(args.file))

    elif args.command == "verify":
        sys.exit(run_service_verify(args.file))

    elif args.command == "replay":
        sys.exit(run_replay_command(args))

    elif args.command == "append":
        sys.exit(run_service_append(args))


if __name__ == "__main__":
    main()
