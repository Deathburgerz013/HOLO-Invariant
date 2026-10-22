import copy

import pytest

from holosim.pytest_collection_continuity import (
    PytestCollectionContinuityError,
    compare_pytest_collections,
    observe_pytest_collection,
)


ALPHA = "test_sample.py::test_alpha"
BETA = "test_sample.py::test_beta"
GAMMA = "test_sample.py::test_gamma"


def observe(*ids):
    return observe_pytest_collection(node_ids=list(ids))


@pytest.mark.parametrize(
    ("current", "status", "missing", "added"),
    [
        ((ALPHA, BETA), "PRESERVED", [], []),
        ((ALPHA, BETA, GAMMA), "PRESERVED", [], [GAMMA]),
        ((ALPHA,), "LOSS_DETECTED", [BETA], []),
        ((ALPHA, GAMMA), "LOSS_DETECTED", [BETA], [GAMMA]),
    ],
)
def test_continuity_boundaries(current, status, missing, added):
    result = compare_pytest_collections(
        previous=observe(ALPHA, BETA),
        current=observe(*current),
    )
    assert result["status"] == status
    assert result["missing"] == missing
    assert result["added"] == added
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_order_independent_identity():
    assert observe(ALPHA, BETA) == observe(BETA, ALPHA)


def test_duplicate_rejected():
    with pytest.raises(PytestCollectionContinuityError):
        observe(ALPHA, ALPHA)


@pytest.mark.parametrize(
    "invalid",
    [None, "abc", [""], [" "], [123], [True], ["bad\x00id"]],
)
def test_malformed_input_rejected(invalid):
    with pytest.raises(PytestCollectionContinuityError):
        observe_pytest_collection(node_ids=invalid)


def test_oversized_identity_rejected():
    with pytest.raises(PytestCollectionContinuityError):
        observe("x" * 4097)


def test_oversized_collection_rejected():
    with pytest.raises(PytestCollectionContinuityError):
        observe_pytest_collection(
            node_ids=[f"test_{i}" for i in range(10001)]
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("count", 999),
        ("node_ids", [ALPHA]),
        ("observation_id", "0" * 64),
        ("accepted", True),
        ("write_authority", "GRANTED"),
    ],
)
def test_tampered_observation_rejected(field, replacement):
    previous = observe(ALPHA, BETA)
    previous[field] = replacement

    with pytest.raises(PytestCollectionContinuityError):
        compare_pytest_collections(
            previous=previous,
            current=observe(ALPHA),
        )


def test_extra_field_rejected():
    previous = observe(ALPHA)
    previous["unexpected"] = True

    with pytest.raises(PytestCollectionContinuityError):
        compare_pytest_collections(
            previous=previous,
            current=observe(ALPHA),
        )


def test_inputs_not_mutated():
    previous = observe(ALPHA, BETA)
    current = observe(ALPHA)
    original_previous = copy.deepcopy(previous)
    original_current = copy.deepcopy(current)

    compare_pytest_collections(previous=previous, current=current)

    assert previous == original_previous
    assert current == original_current


def test_empty_current_collection_detects_total_loss():
    result = compare_pytest_collections(
        previous=observe(ALPHA, BETA),
        current=observe(),
    )
    assert result["missing"] == [ALPHA, BETA]
    assert result["status"] == "LOSS_DETECTED"


def test_empty_previous_collection_does_not_claim_completeness():
    result = compare_pytest_collections(
        previous=observe(),
        current=observe(ALPHA),
    )
    assert result["status"] == "PRESERVED"
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
from pathlib import Path
import json
import subprocess
import sys
import tempfile


def test_isolated_pytest_collection_detects_disappearance():
    collector = """
import json
import sys
import pytest

class Observer:
    def __init__(self):
        self.node_ids = []
        self.finished = False

    def pytest_collection_finish(self, session):
        self.node_ids = [item.nodeid for item in session.items]
        self.finished = True

observer = Observer()

code = pytest.main(
    [sys.argv[1], "--collect-only", "-q", "-p", "no:cacheprovider"],
    plugins=[observer],
)

print("COLLECTION_RESULT=" + json.dumps({
    "exit_code": int(code),
    "finished": observer.finished,
    "node_ids": observer.node_ids,
}))
"""

    def collect(path):
        completed = subprocess.run(
            [sys.executable, "-c", collector, str(path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        results = [
            line.removeprefix("COLLECTION_RESULT=")
            for line in completed.stdout.splitlines()
            if line.startswith("COLLECTION_RESULT=")
        ]

        assert len(results) == 1, completed.stdout + completed.stderr

        result = json.loads(results[0])
        assert result["exit_code"] == 0
        assert result["finished"] is True

        return observe_pytest_collection(node_ids=result["node_ids"])

    with tempfile.TemporaryDirectory() as directory:
        test_file = Path(directory) / "test_sample.py"

        test_file.write_text(
            "def test_alpha():\n"
            "    assert True\n\n"
            "def test_beta():\n"
            "    assert True\n",
            encoding="utf-8",
        )

        before = collect(test_file)

        test_file.write_text(
            "def test_alpha():\n"
            "    assert True\n",
            encoding="utf-8",
        )

        after = collect(test_file)

        result = compare_pytest_collections(
            previous=before,
            current=after,
        )

        assert before["count"] == 2
        assert after["count"] == 1
        assert result["status"] == "LOSS_DETECTED"
        assert len(result["missing"]) == 1
        assert result["missing"][0].endswith("::test_beta")
        assert result["accepted"] is False
        assert result["write_authority"] == "NONE"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("version", True),
        ("count", True),
        ("accepted", 0),
        ("truth_claimed", 0),
    ],
)
def test_observation_rejects_python_equality_type_confusion(
    field, replacement
):
    original = observe(ALPHA)
    tampered = copy.deepcopy(original)
    tampered[field] = replacement

    with pytest.raises(PytestCollectionContinuityError):
        compare_pytest_collections(
            previous=tampered,
            current=original,
        )
