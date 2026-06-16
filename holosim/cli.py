#!/usr/bin/env python3
"""Holo/Sim CLI - Tamper-evident continuity + maintenance tools."""

import argparse
import json
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path

from .core import HoloChain


def generate_master_index(repo_path=".", output="Master_Index_Auto.md"):
    """Improved auto-index: proper header + hash verification + optional chain append."""
    header = """|===========================================| |
| | █†█ Holo/Sim █†█ █†█HSSCE█†█ | |===========================================| |
| Document Title | Master_Index_Auto.md | AUTO-GENERATED | ANCHOR: CANYON_BROCK_HANEY |
|===========================================| |

Auto-generated Master Index — Verified via HOLO/Sim Loop
Generated: {timestamp}
Anchor: Canyon Brock Haney (@CanyonBHaney)
GitHub: https://github.com/Deathburgerz013/HOLO-Invariant
"""

    content = header.format(timestamp=datetime.now().isoformat())
    content += "\nFile Inventory with SHA-256 hashes (for tamper-evidence):\n\n"

    for root, _, files in os.walk(repo_path):
        for f in sorted(files):
            if f.endswith((".md", ".py", ".jsonl", ".toml", ".yaml")) and not f.startswith("Master_Index_Auto"):
                path = os.path.join(root, f)
                try:
                    with open(path, "rb") as fh:
                        hash_val = hashlib.sha256(fh.read()).hexdigest()[:16]
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    rel_path = os.path.relpath(path, repo_path).replace("\\", "/")
                    content += f"- [{f}]({rel_path}) | Last: {mtime.date()} | Hash: {hash_val}...\n"
                except Exception as e:
                    content += f"- {f} (read error: {e})\n"

    with open(output, "w", encoding="utf-8") as f:
        f.write(content)
    return content


def check_spine_headers(directory="."):
    """Improved header checker with better filtering and reporting."""
    issues = []
    header_pattern = re.compile(r"█†█ Holo/Sim █†█")
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".md") and any(kw in file for kw in ["Spine", "Invariant", "HSSCE", "HOLO", "Master_Index", "Core", "Loop"]):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read(5000)  # Limit read for speed
                    if not header_pattern.search(content):
                        issues.append(f"Missing █†█ Holo/Sim █†█ header in {path}")
                except Exception as e:
                    issues.append(f"Read error {path}: {e}")
    return issues


def main():
    parser = argparse.ArgumentParser(description="Holo/Sim CLI - Continuity + Maintenance")
    parser.add_argument("--file", "-f", default="holo_memory.jsonl", help="Chain file path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Existing
    subparsers.add_parser("health", help="Show chain health")
    subparsers.add_parser("review", help="Show entries needing review")

    # New from loop (more robust)
    subparsers.add_parser("index", help="Generate Master_Index_Auto.md with hashes + header")
    subparsers.add_parser("check-spines", help="Validate Holo/Sim headers across spines")

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
        content = generate_master_index()
        print("✅ Master_Index_Auto.md generated successfully.")
        # Optional: Append summary to chain
        # chain.append({"type": "auto_index", "generated_at": datetime.now().isoformat()})
    elif args.command == "check-spines":
        issues = check_spine_headers()
        if issues:
            print("Issues found:")
            for issue in issues:
                print(f"  • {issue}")
        else:
            print("✅ All checked spines compliant with HOLO/Sim header invariant.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()