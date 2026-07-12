"""Read-only feedback engine for HOLO-Invariant Spine artifacts.

This module compares a current artifact against a declared objective, identifies
bounded structural gaps, ranks them, and produces candidate feedback.

It never edits source artifacts.
It never self-approves a correction.
It terminates when no verified difference remains.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


FEEDBACK_TYPE = "holo_spine_feedback_report"
FEEDBACK_VERSION = 1

HEADER_PATTERN = re.compile(r"█†█\s*Holo/Sim\s*█†█")
MARKDOWN_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
SEPARATOR_HEADING = re.compile(
    r"^[ \t]*#?[ \t]*={3,}[ \t]*(.*?)[ \t]*={3,}[ \t]*$",
    re.MULTILINE,
)
WORD_PATTERN = re.compile(r"[a-z0-9]+")

DEFAULT_REQUIRED_SECTIONS = (
    "purpose",
    "objective",
    "verification",
    "uncertainty",
    "termination",
)

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


class SpineFeedbackError(RuntimeError):
    """Base error for feedback failures."""


class FeedbackReadError(SpineFeedbackError):
    """Raised when a source artifact cannot be read."""


@dataclass(frozen=True)
class Section:
    """One structural region discovered in an artifact."""

    index: int
    title: str
    section_id: str
    kind: str
    level: int | None
    start_line: int
    end_line: int
    body: str
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "section_id": self.section_id,
            "kind": self.kind,
            "level": self.level,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class Artifact:
    """Read-only parsed artifact."""

    path: str
    source_hash: str
    header_present: bool
    sections: tuple[Section, ...]

    @property
    def section_ids(self) -> tuple[str, ...]:
        return tuple(section.section_id for section in self.sections)

    def section_map(self) -> dict[str, Section]:
        return {section.section_id: section for section in self.sections}


@dataclass(frozen=True)
class FeedbackItem:
    """One bounded candidate correction."""

    code: str
    severity: str
    category: str
    target: str
    reason: str
    evidence: tuple[str, ...]
    candidate_addition: str
    verification: tuple[str, ...]
    blocks_completion: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "category": self.category,
            "target": self.target,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "candidate_addition": self.candidate_addition,
            "verification": list(self.verification),
            "blocks_completion": self.blocks_completion,
        }


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_title(value: str) -> str:
    words = WORD_PATTERN.findall(value.lower())
    return "_".join(words) or "untitled"


def line_number_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _markers(text: str) -> list[tuple[int, int, str, str, int | None]]:
    candidates: list[tuple[int, int, str, str, int | None]] = []

    for match in MARKDOWN_HEADING.finditer(text):
        title = match.group(2).strip().rstrip("\r")
        candidates.append(
            (
                match.start(),
                match.end(),
                title,
                "markdown_heading",
                len(match.group(1)),
            )
        )

    for match in SEPARATOR_HEADING.finditer(text):
        line = match.group(0).lstrip()
        if line.startswith("# ") or line.startswith("## "):
            continue

        title = match.group(1).strip().strip("|#/*- \t\r")
        if not title:
            continue

        candidates.append(
            (match.start(), match.end(), title, "separator", None)
        )

    by_start: dict[int, tuple[int, int, str, str, int | None]] = {}
    for item in sorted(
        candidates,
        key=lambda value: (
            value[0],
            value[3] != "markdown_heading",
        ),
    ):
        by_start.setdefault(item[0], item)

    return [by_start[key] for key in sorted(by_start)]


def parse_artifact(path: str | Path) -> Artifact:
    resolved = Path(path)

    try:
        raw_bytes = resolved.read_bytes()
        text = raw_bytes.decode("utf-8")
    except OSError as exc:
        raise FeedbackReadError(f"Unable to read {resolved}: {exc}") from exc
    except UnicodeError as exc:
        raise FeedbackReadError(f"{resolved} is not valid UTF-8.") from exc

    markers = _markers(text)
    sections: list[Section] = []
    counts: dict[str, int] = {}

    for index, marker in enumerate(markers):
        start, marker_end, title, kind, level = marker
        end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        body = text[marker_end:end]
        raw = text[start:end]

        normalized = normalize_title(title)
        occurrence = counts.get(normalized, 0) + 1
        counts[normalized] = occurrence
        section_id = (
            normalized
            if occurrence == 1
            else f"{normalized}__{occurrence}"
        )

        sections.append(
            Section(
                index=index,
                title=title,
                section_id=section_id,
                kind=kind,
                level=level,
                start_line=line_number_at(text, start),
                end_line=line_number_at(text, max(start, end - 1)),
                body=body,
                content_hash=sha256_text(raw),
            )
        )

    return Artifact(
        path=resolved.as_posix(),
        source_hash=hashlib.sha256(raw_bytes).hexdigest(),
        header_present=bool(HEADER_PATTERN.search(text[:5000])),
        sections=tuple(sections),
    )


def _contains_terms(text: str, terms: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _find_section_by_terms(
    artifact: Artifact,
    terms: Sequence[str],
) -> Section | None:
    """Find a section using term priority, not merely document order."""
    for term in terms:
        normalized_term = normalize_title(term)
        for section in artifact.sections:
            if (
                section.section_id == normalized_term
                or normalized_term in section.section_id
                or term.lower() in section.title.lower()
            ):
                return section
    return None


def _feedback_code(category: str, target: str) -> str:
    return sha256_text(f"{category}:{target}")[:12]


def _missing_section_feedback(
    section_name: str,
    severity: str,
    reason: str,
) -> FeedbackItem:
    section_title = section_name.replace("_", " ").title()

    return FeedbackItem(
        code=_feedback_code("missing_section", section_name),
        severity=severity,
        category="missing_section",
        target=section_name,
        reason=reason,
        evidence=(f"No section matching '{section_name}' was found.",),
        candidate_addition=(
            f"Add a bounded '{section_title}' section that states only the "
            "minimum information required by the declared objective."
        ),
        verification=(
            f"Confirm the '{section_title}' section is present.",
            "Confirm it does not silently modify another boundary.",
            "Confirm its claims remain traceable to source evidence.",
        ),
        blocks_completion=severity in {"critical", "high"},
    )


def evaluate_feedback(
    artifact: Artifact,
    *,
    objective: str,
    required_sections: Sequence[str] = DEFAULT_REQUIRED_SECTIONS,
) -> dict[str, Any]:
    """Evaluate one artifact against one declared objective."""
    clean_objective = objective.strip()
    if not clean_objective:
        raise SpineFeedbackError("A declared objective is required.")

    items: list[FeedbackItem] = []
    section_ids = set(artifact.section_ids)

    if not artifact.header_present:
        items.append(
            FeedbackItem(
                code=_feedback_code("protocol", "header"),
                severity="critical",
                category="protocol",
                target="canonical_header",
                reason=(
                    "The artifact does not identify the Holo/Sim parsing "
                    "protocol before interpretation."
                ),
                evidence=("Canonical Holo/Sim header was not detected.",),
                candidate_addition=(
                    "Add the canonical Holo/Sim recognition header before "
                    "semantic content."
                ),
                verification=(
                    "Confirm the canonical header is detected.",
                    "Confirm content remains byte-for-byte unchanged otherwise.",
                ),
                blocks_completion=True,
            )
        )

    for required in required_sections:
        if required not in section_ids and not any(
            required in section_id for section_id in section_ids
        ):
            severity = {
                "purpose": "high",
                "objective": "critical",
                "verification": "high",
                "uncertainty": "medium",
                "termination": "high",
            }.get(required, "medium")

            reason = {
                "purpose": "The artifact lacks an explicit reason for existing.",
                "objective": "The feedback loop has no declared target state.",
                "verification": "No explicit acceptance test is defined.",
                "uncertainty": "Unknowns may silently collapse into certainty.",
                "termination": "The loop has no explicit stopping condition.",
            }.get(required, "A required structural distinction is missing.")

            items.append(
                _missing_section_feedback(required, severity, reason)
            )

    objective_section = _find_section_by_terms(
        artifact,
        ("objective", "purpose", "goal"),
    )
    if objective_section is not None:
        objective_words = set(WORD_PATTERN.findall(clean_objective.lower()))
        body_words = set(WORD_PATTERN.findall(objective_section.body.lower()))
        overlap = objective_words & body_words

        if objective_words and len(overlap) / len(objective_words) < 0.25:
            items.append(
                FeedbackItem(
                    code=_feedback_code("objective_drift", objective_section.section_id),
                    severity="high",
                    category="objective_drift",
                    target=objective_section.section_id,
                    reason=(
                        "The declared objective and the artifact's objective-like "
                        "section have weak lexical overlap."
                    ),
                    evidence=(
                        f"Declared objective: {clean_objective}",
                        f"Section: {objective_section.title}",
                    ),
                    candidate_addition=(
                        "Clarify the objective section so it explicitly names "
                        "the declared target without expanding scope."
                    ),
                    verification=(
                        "Compare the revised objective to the declared target.",
                        "Reject unrelated feature expansion.",
                    ),
                    blocks_completion=True,
                )
            )

    verification_section = _find_section_by_terms(
        artifact,
        ("verification", "test", "acceptance"),
    )
    if verification_section is not None:
        verification_text = verification_section.body.strip()
        if not verification_text:
            items.append(
                FeedbackItem(
                    code=_feedback_code(
                        "empty_verification",
                        verification_section.section_id,
                    ),
                    severity="high",
                    category="verification",
                    target=verification_section.section_id,
                    reason="The verification boundary exists but contains no test.",
                    evidence=(
                        f"Section '{verification_section.title}' is empty.",
                    ),
                    candidate_addition=(
                        "Add one reproducible acceptance test tied directly "
                        "to the declared objective."
                    ),
                    verification=(
                        "Run the stated test.",
                        "Record the result without self-approval.",
                    ),
                    blocks_completion=True,
                )
            )

    termination_section = _find_section_by_terms(
        artifact,
        ("termination", "completion", "stop"),
    )
    if termination_section is not None:
        termination_text = termination_section.body.lower()
        if not any(
            phrase in termination_text
            for phrase in (
                "stop",
                "complete",
                "nothing left",
                "no new verified",
                "terminate",
                "reject",
            )
        ):
            items.append(
                FeedbackItem(
                    code=_feedback_code(
                        "weak_termination",
                        termination_section.section_id,
                    ),
                    severity="high",
                    category="termination",
                    target=termination_section.section_id,
                    reason=(
                        "A termination boundary exists, but it does not state "
                        "an executable stopping condition."
                    ),
                    evidence=(
                        f"Section '{termination_section.title}' lacks a clear "
                        "stop signal.",
                    ),
                    candidate_addition=(
                        "State the exact condition under which no further "
                        "candidate correction may be generated."
                    ),
                    verification=(
                        "Confirm the stop condition is objective and testable.",
                        "Confirm the loop can output no-change.",
                    ),
                    blocks_completion=True,
                )
            )

    uncertainty_section = _find_section_by_terms(
        artifact,
        ("uncertainty", "unknown", "unresolved"),
    )
    if uncertainty_section is not None:
        uncertainty_text = uncertainty_section.body.strip()
        if not uncertainty_text:
            items.append(
                FeedbackItem(
                    code=_feedback_code(
                        "empty_uncertainty",
                        uncertainty_section.section_id,
                    ),
                    severity="medium",
                    category="uncertainty",
                    target=uncertainty_section.section_id,
                    reason=(
                        "The uncertainty boundary exists but preserves no "
                        "explicit unresolved state."
                    ),
                    evidence=(
                        f"Section '{uncertainty_section.title}' is empty.",
                    ),
                    candidate_addition=(
                        "Record unresolved questions, or explicitly state that "
                        "no unresolved uncertainty is currently known."
                    ),
                    verification=(
                        "Confirm uncertainty is not silently removed.",
                    ),
                    blocks_completion=False,
                )
            )

    ordered_items = sorted(
        items,
        key=lambda item: (
            SEVERITY_ORDER[item.severity],
            item.category,
            item.target,
        ),
    )

    blocking = [item for item in ordered_items if item.blocks_completion]

    if not ordered_items:
        status = "COMPLETE"
        terminal_signal = "Nothing left for collection in field."
    elif blocking:
        status = "BLOCKED"
        terminal_signal = None
    else:
        status = "REVIEW"
        terminal_signal = None

    report_body = {
        "type": FEEDBACK_TYPE,
        "version": FEEDBACK_VERSION,
        "artifact": {
            "path": artifact.path,
            "source_hash": artifact.source_hash,
            "header_present": artifact.header_present,
            "section_count": len(artifact.sections),
            "ordered_sections": list(artifact.section_ids),
        },
        "objective": clean_objective,
        "status": status,
        "feedback_count": len(ordered_items),
        "blocking_count": len(blocking),
        "feedback": [item.to_dict() for item in ordered_items],
        "terminal_signal": terminal_signal,
        "principle": (
            "Feedback exists to reduce verified difference. "
            "When no verified difference remains, feedback terminates."
        ),
        "interpretation_notice": (
            "Feedback items are bounded proposals derived from visible "
            "structure. They are not accepted corrections."
        ),
    }

    report_hash = sha256_text(
        json.dumps(
            report_body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    return {**report_body, "report_hash": report_hash}


def run_feedback(
    path: str | Path,
    *,
    objective: str,
    required_sections: Sequence[str] = DEFAULT_REQUIRED_SECTIONS,
) -> dict[str, Any]:
    return evaluate_feedback(
        parse_artifact(path),
        objective=objective,
        required_sections=required_sections,
    )


def run_self_test() -> None:
    complete = """|===========================================|
| █†█ Holo/Sim █†█ █†█ HSSCE █†█ |
|===========================================|

# Purpose
Preserve a bounded reconstruction process.

# Objective
Produce the smallest verified correction required by the artifact.

# Verification
Run the parser and confirm the declared sections remain detectable.

# Uncertainty
No unresolved uncertainty is currently known.

# Termination
Stop when no new verified difference remains.
"""

    incomplete = """# Purpose
Do more things.

# Verification
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        complete_path = root / "complete.md"
        incomplete_path = root / "incomplete.md"

        complete_path.write_bytes(complete.encode("utf-8"))
        incomplete_path.write_bytes(incomplete.encode("utf-8"))

        complete_report = run_feedback(
            complete_path,
            objective=(
                "Produce the smallest verified correction required "
                "by the artifact."
            ),
        )
        incomplete_report = run_feedback(
            incomplete_path,
            objective="Produce bounded verified feedback.",
        )

    assert complete_report["status"] == "COMPLETE"
    assert complete_report["feedback_count"] == 0
    assert (
        complete_report["terminal_signal"]
        == "Nothing left for collection in field."
    )

    assert incomplete_report["status"] == "BLOCKED"
    assert incomplete_report["blocking_count"] >= 1
    assert any(
        item["target"] == "canonical_header"
        for item in incomplete_report["feedback"]
    )
    assert any(
        item["target"] == "termination"
        for item in incomplete_report["feedback"]
    )

    print("✅ Spine feedback self-test passed.")


def _print_json(value: Mapping[str, Any]) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate bounded, read-only feedback for one Spine artifact."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Compare one artifact against one declared objective",
    )
    analyze_parser.add_argument("file")
    analyze_parser.add_argument(
        "--objective",
        required=True,
        help="Declared objective used for gap analysis",
    )
    analyze_parser.add_argument(
        "--require",
        action="append",
        default=None,
        help=(
            "Required normalized section name. Repeat to override defaults."
        ),
    )
    analyze_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional JSON report path",
    )

    subparsers.add_parser(
        "self-test",
        help="Run isolated feedback tests",
    )

    args = parser.parse_args()

    try:
        if args.command == "analyze":
            required = (
                tuple(args.require)
                if args.require
                else DEFAULT_REQUIRED_SECTIONS
            )

            report = run_feedback(
                args.file,
                objective=args.objective,
                required_sections=required,
            )

            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(
                        report,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                print(f"Feedback report written: {output_path}")
            else:
                _print_json(report)

            raise SystemExit(0 if report["status"] == "COMPLETE" else 1)

        if args.command == "self-test":
            run_self_test()
            raise SystemExit(0)

        raise SystemExit(f"Unknown command: {args.command}")
    except SpineFeedbackError as exc:
        print(f"Spine feedback: FAIL\n{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()