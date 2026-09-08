from __future__ import annotations

import importlib
import inspect


CANDIDATE_MODULES = (
    "holosim.organizer",
    "holosim.next_check_organizer",
    "holosim.check_organizer",
    "holosim.uncertainty_ledger",
)


def _candidate_callables():
    discovered = []
    for module_name in CANDIDATE_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue

        for name, value in vars(module).items():
            if not callable(value):
                continue
            lowered = name.lower()
            if (
                ("next" in lowered and "check" in lowered)
                or ("organ" in lowered)
                or ("resolution" in lowered and "condition" in lowered)
            ):
                discovered.append((module_name, name, value))
    return discovered


def test_repo_exposes_a_read_only_next_check_organizer_contract():
    """
    Characterize whether current production code already exposes a deterministic,
    read-only operation that can derive the next eligible check from existing
    unresolved records without inventing missing conditions or mutating state.

    This test is intentionally expected to fail if no such production surface exists.
    It does not prescribe an implementation name.
    """
    candidates = _candidate_callables()

    assert candidates, (
        "No production callable was found that exposes a next-check organizer "
        "surface. Current code records uncertainty and resolution conditions, "
        "but this characterization could not find an operation that turns those "
        "existing records into an explicit next-check candidate."
    )

    readable = []
    for module_name, name, value in candidates:
        try:
            signature = inspect.signature(value)
        except (TypeError, ValueError):
            continue
        readable.append(f"{module_name}.{name}{signature}")

    assert readable, (
        "Candidate organizer-like callables existed, but none exposed an "
        "inspectable callable contract."
    )
