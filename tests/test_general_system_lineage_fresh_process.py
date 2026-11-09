
"""Fresh-process reconstruction of general system lineage."""

import json
import subprocess
import sys

import pytest

from holosim.canonical import stable_hash
from holosim.general_system_lineage import (
    build_general_system_lineage,
)


def make_report():
    systems = [
        {
            "system_id": "system-b",
            "domain": "software",
            "label": "Controller",
        },
        {
            "system_id": "system-a",
            "domain": "hardware",
            "label": "Sensor",
        },
    ]

    observations = [
        {
            "observation_id": "observation-a",
            "system_id": "system-a",
            "source_id": "source-a",
            "boundary": "test-boundary",
            "evidence_hash": "a" * 64,
            "finding": {"value": 42},
        }
    ]

    relationship = {
        "relationship_id": "relationship-a",
        "source_system_id": "system-a",
        "target_system_id": "system-b",
        "relationship_type": "reports_to",
        "evidence_observation_ids": ["observation-a"],
        "status": "PROPOSED",
    }

    first = {
        "correction_id": "correction-z",
        "target_record_hash": stable_hash(relationship),
        "evidence_observation_ids": ["observation-a"],
        "assessment": "Initial correction",
    }

    second = {
        "correction_id": "correction-a",
        "target_record_hash": stable_hash(first),
        "evidence_observation_ids": ["observation-a"],
        "assessment": "Correction of prior correction",
    }

    return build_general_system_lineage(
        systems,
        observations,
        [relationship],
        [first, second],
    )


CHILD = """
import json
import sys

from holosim.general_system_lineage import (
    build_general_system_lineage,
    validate_general_system_lineage,
)

report = json.loads(sys.stdin.read())

validated = validate_general_system_lineage(report)

rebuilt = build_general_system_lineage(
    report["systems"],
    report["observations"],
    report["relationships"],
    report["corrections"],
)

print(json.dumps({
    "validated": validated,
    "identity_equal": rebuilt["lineage_hash"] == report["lineage_hash"],
    "report_equal": rebuilt == report,
    "correction_order": [
        item["correction_id"]
        for item in rebuilt["corrections"]
    ],
    "truth_claimed": rebuilt["truth_claimed"],
    "accepted": rebuilt["accepted"],
    "write_authority": rebuilt["write_authority"],
}))
"""


def run_child(report):
    return subprocess.run(
        [sys.executable, "-c", CHILD],
        input=json.dumps(report),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


def test_fresh_process_reconstructs_identical_lineage():
    report = make_report()
    result = run_child(report)

    assert result.returncode == 0, result.stderr

    output = json.loads(result.stdout)

    assert output["validated"] is True
    assert output["identity_equal"] is True
    assert output["report_equal"] is True

    assert output["correction_order"] == [
        "correction-z",
        "correction-a",
    ]

    assert output["truth_claimed"] is False
    assert output["accepted"] is False
    assert output["write_authority"] == "NONE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("truth_claimed", True),
        ("accepted", True),
        ("write_authority", "WRITE"),
        ("lineage_hash", "0" * 64),
    ],
)
def test_fresh_process_rejects_tampered_report(field, value):
    report = make_report()
    report[field] = value

    result = run_child(report)

    assert result.returncode != 0


def test_fresh_process_rejects_reordered_correction_chain():
    report = make_report()

    report["corrections"].reverse()

    result = run_child(report)

    assert result.returncode != 0
