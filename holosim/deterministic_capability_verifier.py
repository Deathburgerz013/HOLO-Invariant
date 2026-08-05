"""Deterministic verification for explicit software capability contracts.

This verifier does not infer executable checks from natural-language
requirements. A capability must provide an explicit verification object
before deterministic verification can proceed.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping

from holosim.canonical import stable_hash


RECEIPT_TYPE = "deterministic_capability_verification_receipt"
RECEIPT_VERSION = 1


class DeterministicCapabilityVerifierError(ValueError):
    """Raised when verifier input is invalid."""


class DeterministicCapabilityVerifier:
    """Verify only explicitly declared capability checks."""

    def __init__(self) -> None:
        self.last_receipt: dict[str, Any] | None = None

    def bind(
        self,
        capability: Mapping[str, Any],
    ) -> Callable[[str | Path], dict[str, Any]]:
        """Bind one capability to the builder's one-argument verifier shape."""

        if not isinstance(capability, Mapping):
            raise TypeError("capability must be a mapping")

        bound_capability = deepcopy(dict(capability))

        def bound_verifier(
            workspace: str | Path,
        ) -> dict[str, Any]:
            return self(
                deepcopy(bound_capability),
                workspace,
            )

        return bound_verifier

    def __call__(
        self,
        capability: Mapping[str, Any],
        workspace: str | Path,
    ) -> dict[str, Any]:
        if not isinstance(capability, Mapping):
            raise TypeError("capability must be a mapping")

        workspace_path = Path(workspace).resolve()

        if not workspace_path.is_dir():
            raise DeterministicCapabilityVerifierError(
                "workspace must be an existing directory"
            )

        capability_record = deepcopy(dict(capability))
        verification = capability_record.get("verification")

        if not isinstance(verification, Mapping):
            return self._receipt(
                capability_record,
                workspace_path,
                passed=False,
                verified=False,
                reason="CAPABILITY_VERIFICATION_SPEC_MISSING",
                checks=[],
            )

        required_files = verification.get("required_files")

        if (
            not isinstance(required_files, list)
            or not required_files
            or any(
                not isinstance(path, str)
                or not path.strip()
                for path in required_files
            )
        ):
            return self._receipt(
                capability_record,
                workspace_path,
                passed=False,
                verified=False,
                reason="CAPABILITY_VERIFICATION_SPEC_UNSUPPORTED",
                checks=[],
            )

        checks: list[dict[str, Any]] = []

        for relative_path in required_files:
            candidate = Path(relative_path)
            posix_candidate = PurePosixPath(relative_path)
            windows_candidate = PureWindowsPath(relative_path)

            if (
                posix_candidate.is_absolute()
                or windows_candidate.is_absolute()
                or bool(windows_candidate.drive)
                or ".." in posix_candidate.parts
                or ".." in windows_candidate.parts
            ):
                return self._receipt(
                    capability_record,
                    workspace_path,
                    passed=False,
                    verified=False,
                    reason="CAPABILITY_VERIFICATION_PATH_INVALID",
                    checks=checks,
                )

            target = workspace_path / candidate

            checks.append(
                {
                    "type": "required_file",
                    "path": candidate.as_posix(),
                    "passed": target.is_file(),
                }
            )

        passed = all(
            check["passed"] is True
            for check in checks
        )

        return self._receipt(
            capability_record,
            workspace_path,
            passed=passed,
            verified=passed,
            reason=(
                "CAPABILITY_VERIFIED"
                if passed
                else "CAPABILITY_VERIFICATION_FAILED"
            ),
            checks=checks,
        )

    def _receipt(
        self,
        capability: dict[str, Any],
        workspace: Path,
        *,
        passed: bool,
        verified: bool,
        reason: str,
        checks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": RECEIPT_TYPE,
            "version": RECEIPT_VERSION,
            "capability": capability,
            "workspace": str(workspace),
            "passed": passed,
            "verified": verified,
            "reason": reason,
            "checks": deepcopy(checks),
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }

        receipt = {
            **body,
            "receipt_hash": stable_hash(body),
        }

        self.last_receipt = deepcopy(receipt)
        return receipt


def build_deterministic_capability_verifier(
    **kwargs: Any,
) -> DeterministicCapabilityVerifier:
    """Build one deterministic capability verifier."""

    return DeterministicCapabilityVerifier(**kwargs)