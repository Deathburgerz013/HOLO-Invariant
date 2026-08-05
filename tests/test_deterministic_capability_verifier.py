from pathlib import Path

import pytest

from holosim.deterministic_capability_verifier import (
    build_deterministic_capability_verifier,
)


def test_capability_without_verification_spec_is_not_verified(
    tmp_path: Path,
):
    verifier = build_deterministic_capability_verifier()

    result = verifier(
        {
            "id": "calculator.history",
            "requirement": "track calculation history",
            "depends_on": [],
        },
        tmp_path,
    )

    assert result["passed"] is False
    assert result["verified"] is False
    assert (
        result["reason"]
        == "CAPABILITY_VERIFICATION_SPEC_MISSING"
    )
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_explicit_required_file_check_passes_when_file_exists(
    tmp_path: Path,
):
    (tmp_path / "calculator.py").write_text(
        "class Calculator:\n    pass\n",
        encoding="utf-8",
    )

    verifier = build_deterministic_capability_verifier()

    result = verifier(
        {
            "id": "calculator.module",
            "requirement": "provide calculator module",
            "depends_on": [],
            "verification": {
                "required_files": [
                    "calculator.py",
                ],
            },
        },
        tmp_path,
    )

    assert result["passed"] is True
    assert result["verified"] is True
    assert result["reason"] == "CAPABILITY_VERIFIED"
    assert result["checks"] == [
        {
            "type": "required_file",
            "path": "calculator.py",
            "passed": True,
        }
    ]


def test_explicit_required_file_check_fails_when_file_is_missing(
    tmp_path: Path,
):
    verifier = build_deterministic_capability_verifier()

    result = verifier(
        {
            "id": "calculator.module",
            "requirement": "provide calculator module",
            "depends_on": [],
            "verification": {
                "required_files": [
                    "calculator.py",
                ],
            },
        },
        tmp_path,
    )

    assert result["passed"] is False
    assert result["verified"] is False
    assert (
        result["reason"]
        == "CAPABILITY_VERIFICATION_FAILED"
    )
    assert result["checks"] == [
        {
            "type": "required_file",
            "path": "calculator.py",
            "passed": False,
        }
    ]


@pytest.mark.parametrize(
    ("verification", "reason"),
    [
        (
            {"required_files": []},
            "CAPABILITY_VERIFICATION_SPEC_UNSUPPORTED",
        ),
        (
            {"required_files": [r"C:\outside.py"]},
            "CAPABILITY_VERIFICATION_PATH_INVALID",
        ),
        (
            {"required_files": ["../outside.py"]},
            "CAPABILITY_VERIFICATION_PATH_INVALID",
        ),
    ],
)
def test_invalid_required_file_specs_are_rejected(
    tmp_path: Path,
    verification,
    reason,
):
    verifier = build_deterministic_capability_verifier()

    result = verifier(
        {
            "id": "calculator.module",
            "requirement": "provide calculator module",
            "depends_on": [],
            "verification": verification,
        },
        tmp_path,
    )

    assert result["passed"] is False
    assert result["verified"] is False
    assert result["reason"] == reason
def test_bound_verifier_uses_one_argument_builder_contract(
    tmp_path: Path,
):
    (tmp_path / "calculator.py").write_text(
        "class Calculator:\n    pass\n",
        encoding="utf-8",
    )

    verifier = build_deterministic_capability_verifier()

    bound = verifier.bind(
        {
            "id": "calculator.module",
            "requirement": "provide calculator module",
            "depends_on": [],
            "verification": {
                "required_files": ["calculator.py"],
            },
        }
    )

    result = bound(tmp_path)

    assert result["passed"] is True
    assert result["verified"] is True
    assert result["reason"] == "CAPABILITY_VERIFIED"