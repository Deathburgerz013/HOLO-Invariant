import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

import holosim.holo_cli as cli
from holosim.public_continuity_benchmark import (
    PUBLIC_CONDITION_TYPE,
    PublicContinuityBenchmarkError,
    load_public_continuity_fixture,
    run_public_continuity_benchmark,
    score_public_continuity_condition,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "benchmarks"
    / "continuity-v1.fixture.json"
)
EXAMPLE_PATH = (
    ROOT
    / "benchmarks"
    / "examples"
    / "passing-condition.json"
)
SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "continuity-condition.schema.json"
)


def load_example():
    return json.loads(
        EXAMPLE_PATH.read_text(encoding="utf-8")
    )


def test_public_fixture_and_example_are_committed():
    assert FIXTURE_PATH.is_file()
    assert EXAMPLE_PATH.is_file()
    assert SCHEMA_PATH.is_file()

    fixture = load_public_continuity_fixture(
        FIXTURE_PATH
    )
    example = load_example()

    assert fixture["benchmark_id"] == (
        "holo-public-continuity-v1"
    )
    assert example["type"] == PUBLIC_CONDITION_TYPE
    assert example["version"] == 1
    assert example["fixture_hash"] == fixture[
        "fixture_hash"
    ]


def test_public_condition_scores_against_exact_fixture():
    fixture = load_public_continuity_fixture(
        FIXTURE_PATH
    )

    result = score_public_continuity_condition(
        fixture=fixture,
        condition=load_example(),
    )

    assert result["condition_id"] == (
        "example-bounded-continuity"
    )
    assert result["fixture_hash"] == fixture[
        "fixture_hash"
    ]
    assert result["metrics"] == {
        "latest_justified_recall": 1.0,
        "superseded_resurrection_count": 0,
        "uncertainty_recall": 1.0,
        "lineage_recall": 1.0,
        "stale_continuation_blocked": True,
        "passes_bounded_continuity_fixture": True,
    }
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_public_condition_contract_is_closed():
    fixture = load_public_continuity_fixture(
        FIXTURE_PATH
    )
    condition = load_example()
    condition["approval"] = "GRANTED"

    with pytest.raises(
        PublicContinuityBenchmarkError,
        match="condition fields are invalid",
    ):
        score_public_continuity_condition(
            fixture=fixture,
            condition=condition,
        )


def test_condition_cannot_select_different_fixture():
    fixture = load_public_continuity_fixture(
        FIXTURE_PATH
    )
    condition = load_example()
    condition["fixture_hash"] = "different-fixture"

    with pytest.raises(
        PublicContinuityBenchmarkError,
        match="condition fixture_hash does not match",
    ):
        score_public_continuity_condition(
            fixture=fixture,
            condition=condition,
        )


def test_tampered_public_fixture_is_rejected(tmp_path):
    fixture = json.loads(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )
    fixture["latest_justified_claim_ids"] = [
        "tampered-current"
    ]
    path = tmp_path / "tampered.json"
    path.write_text(
        json.dumps(fixture),
        encoding="utf-8",
    )

    with pytest.raises(
        PublicContinuityBenchmarkError,
        match="fixture hash does not match content",
    ):
        load_public_continuity_fixture(path)


def test_public_scoring_is_deterministic():
    fixture = load_public_continuity_fixture(
        FIXTURE_PATH
    )
    condition = load_example()

    first = score_public_continuity_condition(
        fixture=fixture,
        condition=condition,
    )
    second = score_public_continuity_condition(
        fixture=fixture,
        condition=condition,
    )

    assert first == second
    assert first["result_hash"] == second[
        "result_hash"
    ]


def test_runner_prints_machine_readable_result(capsys):
    args = argparse.Namespace(
        benchmark_kind="continuity",
        condition=str(EXAMPLE_PATH),
        fixture=str(FIXTURE_PATH),
    )

    exit_code = run_public_continuity_benchmark(
        args
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert exit_code == 0
    assert captured.err == ""
    assert result["condition_id"] == (
        "example-bounded-continuity"
    )
    assert result["metrics"][
        "passes_bounded_continuity_fixture"
    ] is True


def test_runner_reports_invalid_input_without_traceback(
    tmp_path,
    capsys,
):
    invalid = tmp_path / "invalid.json"
    invalid.write_text(
        '{"type":"wrong"}',
        encoding="utf-8",
    )
    args = argparse.Namespace(
        benchmark_kind="continuity",
        condition=str(invalid),
        fixture=str(FIXTURE_PATH),
    )

    exit_code = run_public_continuity_benchmark(
        args
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Continuity benchmark blocked:" in (
        captured.err
    )


def test_holo_benchmark_continuity_entrypoint(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "holo",
            "benchmark",
            "continuity",
            "--condition",
            str(EXAMPLE_PATH),
            "--fixture",
            str(FIXTURE_PATH),
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["metrics"][
        "passes_bounded_continuity_fixture"
    ] is True


def test_schema_closes_public_condition_contract():
    schema = json.loads(
        SCHEMA_PATH.read_text(encoding="utf-8")
    )

    assert schema["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "type",
        "version",
        "fixture_hash",
        "condition_id",
        "recovered_claim_ids",
        "claimed_current_claim_ids",
        "preserved_uncertainty_claim_ids",
        "reconstructed_lineage_edges",
        "stale_continuation_decision",
    }