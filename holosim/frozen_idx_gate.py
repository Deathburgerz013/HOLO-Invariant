"""Fail-closed admission gate for a frozen IDX and moving Spine slots."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Sequence


SlotHash = tuple[str, str]
SlotPayload = tuple[str, str]


@dataclass(frozen=True)
class IDXGateResult:
    """Read-only result of comparing transported slots with a frozen IDX."""

    status: str
    code: str
    fused: bool = False
    slot: str | None = None
    expected: str | None = None
    observed: str | None = None


class FrozenIDXGate:
    """Compare moving slot payloads against an immutable ordered IDX."""

    def __init__(
        self,
        *,
        version: int,
        slots: Sequence[SlotHash],
    ) -> None:
        frozen_slots = tuple(slots)

        if version < 1:
            raise ValueError("IDX version must be at least 1.")

        if not frozen_slots:
            raise ValueError("Frozen IDX must contain at least one slot.")

        names = [name for name, _ in frozen_slots]

        if any(not name or not expected_hash for name, expected_hash in frozen_slots):
            raise ValueError("IDX slot names and hashes must be non-empty.")

        if len(names) != len(set(names)):
            raise ValueError("Frozen IDX cannot contain duplicate slot names.")

        self._version = version
        self._slots = frozen_slots

    @property
    def version(self) -> int:
        return self._version

    @property
    def slots(self) -> tuple[SlotHash, ...]:
        return self._slots

    def check(
        self,
        *,
        version: int,
        slots: Sequence[SlotPayload],
    ) -> IDXGateResult:
        transported = tuple(slots)

        if version != self._version:
            return IDXGateResult(
                status="ABORT",
                code="VERSION_MISMATCH",
                expected=str(self._version),
                observed=str(version),
            )

        expected_names = tuple(name for name, _ in self._slots)
        observed_names = tuple(name for name, _ in transported)

        for name in expected_names:
            if name not in observed_names:
                return IDXGateResult(
                    status="ABORT",
                    code="SLOT_MISSING",
                    slot=name,
                )

        for name in observed_names:
            if name not in expected_names:
                return IDXGateResult(
                    status="ABORT",
                    code="SLOT_UNEXPECTED",
                    slot=name,
                )

        if observed_names != expected_names:
            return IDXGateResult(
                status="ABORT",
                code="SLOT_ORDER_MISMATCH",
                expected=",".join(expected_names),
                observed=",".join(observed_names),
            )

        for (expected_name, expected_hash), (observed_name, payload) in zip(
            self._slots,
            transported,
            strict=True,
        ):
            observed_hash = sha256(payload.encode("utf-8")).hexdigest()

            if observed_hash != expected_hash:
                return IDXGateResult(
                    status="ABORT",
                    code="SLOT_HASH_MISMATCH",
                    slot=expected_name,
                    expected=expected_hash,
                    observed=observed_hash,
                )

            if observed_name != expected_name:
                return IDXGateResult(
                    status="ABORT",
                    code="SLOT_ORDER_MISMATCH",
                    slot=observed_name,
                )

        return IDXGateResult(
            status="PASS",
            code="IDX_MATCH",
        )