import json
from pathlib import Path

from holosim.public_continuity_benchmark import (
    load_public_continuity_fixture,
    score_public_continuity_condition,
)


ROOT = Path(__file__).resolve().parents[1]

FIXTURE_PATH = (
    ROOT
    / "benchmarks"
    / "continuity-v1.fixture.json"
)
CONDITION_PATH = (
    ROOT
    / "benchmarks"
    / "examples"
    / "passing-condition.json"
)
RESULT_PATH = (
    ROOT
    / "benchmarks"
    / "results"
    / "holo-reference.result.json"
)
WORKFLOW_PATH = (
    ROOT
    / ".github"
    / "workflows"
    / "benchmark.yml"
)


def load_json(path: Path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def test_committed_reference_result_matches_current_scorer():
    assert RESULT_PATH.is_file()

    fixture = load_public_continuity_fixture(
        FIXTURE_PATH
    )
    condition = load_json(CONDITION_PATH)
    expected = score_public_continuity_condition(
        fixture=fixture,
        condition=condition,
    )

    assert load_json(RESULT_PATH) == expected


def test_reference_result_remains_bounded():
    result = load_json(RESULT_PATH)

    assert result["metrics"][
        "passes_bounded_continuity_fixture"
    ] is True
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_benchmark_workflow_reproduces_and_compares_result():
    workflow = WORKFLOW_PATH.read_text(
        encoding="utf-8"
    )

    assert "name: Continuity Benchmark" in workflow
    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow

    assert (
        "python -m holosim.holo_cli benchmark continuity"
        in workflow
    )
    assert (
        "benchmarks/examples/passing-condition.json"
        in workflow
    )
    assert (
        "benchmarks/results/holo-reference.result.json"
        in workflow
    )
    assert "diff -u" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_readme_exposes_ci_verified_benchmark():
    readme = (ROOT / "README.md").read_text(
        encoding="utf-8"
    )

    badge = (
        "actions/workflows/benchmark.yml/"
        "badge.svg?branch=main"
    )
    assert badge in readme
    assert "CI-verified reference result" in readme
    assert (
        "benchmarks/results/"
        "holo-reference.result.json"
    ) in readme

    assert (
        "| Latest justified recall | `1.0` |"
        in readme
    )
    assert (
        "| Superseded resurrection count | `0` |"
        in readme
    )
    assert (
        "| Uncertainty recall | `1.0` |"
        in readme
    )
    assert (
        "| Lineage recall | `1.0` |"
        in readme
    )
    assert (
        "| Stale continuation blocked | `true` |"
        in readme
    )