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
    from holosim.core import HoloChain
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.core import HoloChain


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
        ).strip() or "Unknown"
    except Exception:
        return "Unavailable"


def generate_master_index(repo_path: str = ".", output: str = "Master_Index_Auto.md") -> str:
    """Generate a verified file inventory with SHA-256 hashes."""
    repo_root = Path(repo_path).resolve()
    output_path = repo_root / output

    header = """|===========================================| |
| | █†█ Holo/Sim █†█ █†█HSSCE█†█ | |===========================================| |
| Document Title | Master_Index_Auto.md | AUTO-GENERATED | ANCHOR: CANYON_BROCK_HANEY |
|===========================================| |

Auto-generated Master Index — Verified via HOLO/Sim Loop
Generated: {timestamp}
Anchor: Canyon Brock Haney (@CanyonBHaney)
GitHub: https://github.com/Deathburgerz013/HOLO-Invariant

File Inventory with SHA-256 hashes (for tamper-evidence):

"""

    content = header.format(timestamp=datetime.now().isoformat())

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


def check_spine_headers(directory: str = ".") -> list[str]:
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

    repo_root = Path(".").resolve()
    chain_file = Path(chain.file_path)

    print(f"CLI Version ............. {chain.VERSION}")
    print(f"Python .................. {platform.python_version()}")
    print(f"Platform ................ {platform.system()} {platform.release()}")
    print()

    git_ok = (repo_root / ".git").exists()
    print(f"Repository .............. {'PASS' if git_ok else 'NOT FOUND'}")
    print(f"Git Branch .............. {get_git_branch()}")
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
        "Master Index": Path("Master_Index.md").exists() or Path("Master_Index_Auto.md").exists(),
        "IDX Manager": Path("holosim/idx_manager.py").exists(),
        "Rebirth Engine": Path("holosim/rebirth_engine.py").exists(),
        "Artifact Parser": Path("holosim/artifact_parser.py").exists(),
        "Boot Integration": Path("holosim/boot_integration.py").exists(),
        "Core": Path("holosim/core.py").exists(),
        "CLI": Path("holosim/holo_cli.py").exists(),
    }

    failed = False
    for name, passed in checks.items():
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Holo/Sim CLI - Continuity + Maintenance")
    parser.add_argument("--file", "-f", default="holo_memory.jsonl", help="Chain file path")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health", help="Show chain health")
    subparsers.add_parser("review", help="Show entries needing review")
    subparsers.add_parser("index", help="Generate Master_Index_Auto.md with hashes + header")
    subparsers.add_parser("check-spines", help="Validate Holo/Sim headers across spines")
    subparsers.add_parser("test", help="Run complete Holo/Sim self-test")
    subparsers.add_parser("doctor", help="Inspect Holo/Sim installation")

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


if __name__ == "__main__":
    main()