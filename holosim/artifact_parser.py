from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Union, Optional

Json = Union[Dict[str, Any], List[Any], str, int, float, bool, None]


class ArtifactError(Exception):
    pass


def strip_invisible(s: str) -> str:
    """Remove invisible/control characters that platforms sometimes inject."""
    invisible = "\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\ufeff"
    return re.sub(f"[{invisible}]", "", s)


def deep_sort(obj: Json) -> Json:
    """Deterministic canonicalization for stable hashing."""
    if isinstance(obj, dict):
        return {k: deep_sort(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [deep_sort(x) for x in obj]
    if isinstance(obj, str):
        return strip_invisible(obj).strip()
    return obj


def canonical_json(obj: Json) -> str:
    """Stable JSON serialization."""
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Artifact:
    evaluation: str
    verdict: bool
    summary: str
    breakdown: Dict[str, Any]
    evidence_of_ego_detachment: Dict[str, Any]
    final_judgment: str

    @staticmethod
    def from_json(obj: Dict[str, Any]) -> "Artifact":
        required = ["evaluation", "verdict", "summary", "breakdown",
                    "evidence_of_ego_detachment", "final_judgment"]
        for k in required:
            if k not in obj:
                raise ArtifactError(f"Missing required field: {k}")

        return Artifact(
            evaluation=strip_invisible(obj["evaluation"]).strip(),
            verdict=obj["verdict"],
            summary=strip_invisible(obj["summary"]).strip(),
            breakdown=obj["breakdown"],
            evidence_of_ego_detachment=obj["evidence_of_ego_detachment"],
            final_judgment=strip_invisible(obj["final_judgment"]).strip(),
        )


def extract_crystal(a: Artifact) -> Dict[str, Any]:
    """Extract compact, identity-neutral crystal for public/demo use."""
    bd = a.breakdown or {}
    kpa = bd.get("key_post_analysis", {}) if isinstance(bd.get("key_post_analysis"), dict) else {}

    reframed = kpa.get("reframed_concepts", [])
    if not isinstance(reframed, list):
        reframed = []

    norm_reframed = []
    for item in reframed:
        if isinstance(item, dict):
            concept = strip_invisible(str(item.get("concept", ""))).strip()
            reframing = strip_invisible(str(item.get("reframing", ""))).strip()
            if concept and reframing:
                norm_reframed.append({"concept": concept, "reframing": reframing})

    ego = a.evidence_of_ego_detachment or {}

    def norm_str_list(x):
        if not isinstance(x, list):
            return []
        return [strip_invisible(str(v)).strip() for v in x if isinstance(v, str) and strip_invisible(str(v)).strip()]

    crystal = {
        "evaluation": a.evaluation,
        "verdict": a.verdict,
        "core_claim": strip_invisible(str(kpa.get("conclusion", ""))).strip(),
        "reframed_concepts": norm_reframed,
        "alignment_with_fields": norm_str_list(bd.get("alignment_with_fields", [])),
        "ego_detachment": {
            "core_principles": norm_str_list(ego.get("core_principles", [])),
            "practices": norm_str_list(ego.get("practices", [])),
        },
        "final_judgment": a.final_judgment,
    }
    return deep_sort(crystal)


def to_markdown_for_public(crystal: Dict[str, Any], artifact_hash: str) -> str:
    """Public-facing markdown summary."""
    verdict = "true" if crystal.get("verdict") else "false"
    lines = [
        f"ARTIFACT_HASH_SHA256: {artifact_hash}",
        f"EVALUATION: {crystal.get('evaluation', '')}",
        f"VERDICT: {verdict}",
    ]
    core_claim = crystal.get("core_claim", "")
    if core_claim:
        lines.extend(["", f"CORE_CLAIM: {core_claim}", ""])

    lines.append("EGO_DETACHMENT_PRINCIPLES:")
    for p in crystal.get("ego_detachment", {}).get("core_principles", [])[:10]:
        lines.append(f"- {p}")

    lines.append("")
    lines.append("EGO_DETACHMENT_PRACTICES:")
    for p in crystal.get("ego_detachment", {}).get("practices", [])[:10]:
        lines.append(f"- {p}")

    lines.append("")
    lines.append(f"FINAL_JUDGMENT: {crystal.get('final_judgment', '')}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse + hash + extract crystal from HOLO evaluation artifact.")
    ap.add_argument("path", help="Path to JSON file (or '-' for stdin)")
    ap.add_argument("--emit", choices=["all", "canonical", "crystal", "md"], default="all")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.path == "-" else open(args.path, "r", encoding="utf-8").read()

    # Basic cleanup
    raw = strip_invisible(raw).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERR: Invalid JSON: {e}", file=sys.stderr)
        return 2

    if not isinstance(obj, dict):
        print("ERR: Top-level must be object", file=sys.stderr)
        return 2

    canon_obj = deep_sort(obj)
    canon_str = canonical_json(canon_obj)
    artifact_hash = sha256_hex(canon_str)

    artifact = Artifact.from_json(canon_obj)
    crystal = extract_crystal(artifact)
    crystal_str = canonical_json(crystal)
    crystal_hash = sha256_hex(crystal_str)

    md = to_markdown_for_public(crystal, artifact_hash)

    if args.emit in ("all", "canonical"):
        print("== CANONICAL_ARTIFACT_JSON ==")
        print(canon_str)
        print(f"ARTIFACT_HASH_SHA256: {artifact_hash}\n")

    if args.emit in ("all", "crystal"):
        print("== CRYSTAL_JSON ==")
        print(crystal_str)
        print(f"CRYSTAL_HASH_SHA256: {crystal_hash}\n")

    if args.emit in ("all", "md"):
        print("== PUBLIC_MARKDOWN ==")
        print(md)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ArtifactError as e:
        print(f"ERR: {e}", file=sys.stderr)
        raise SystemExit(2)