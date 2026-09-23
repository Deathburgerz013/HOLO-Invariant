"""Bounded verified generations for memory-card recorded state."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .memory_card import (
    MemoryCardError,
    load_memory_card,
    save_memory_card,
)


class MemoryCardGenerationError(MemoryCardError):
    """Raised when generation storage cannot satisfy its contract."""


def _generation_dir(path: str | Path) -> Path:
    target = Path(path)
    return target.parent / f".{target.name}.generations"


def _generation_path(path: str | Path, generation: int) -> Path:
    return _generation_dir(path) / f"generation-{generation:06d}.json"


def _read_generation(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoryCardGenerationError(
            f"unable to read generation: {path}"
        ) from exc

    if type(value) is not dict:
        raise MemoryCardGenerationError(
            "stored generation must be a plain dictionary"
        )

    return value


def _list_generation_paths(path: str | Path) -> list[Path]:
    directory = _generation_dir(path)

    if not directory.exists():
        return []

    if not directory.is_dir():
        raise MemoryCardGenerationError(
            "generation storage path must be a directory"
        )

    paths = sorted(directory.glob("generation-*.json"))

    for candidate in paths:
        try:
            int(candidate.stem.split("-", 1)[1])
        except (IndexError, ValueError) as exc:
            raise MemoryCardGenerationError(
                "invalid generation filename"
            ) from exc

    return paths


def list_memory_card_generations(
    path: str | Path,
) -> list[dict[str, Any]]:
    """Return verified generations in ascending generation order."""

    result: list[dict[str, Any]] = []

    for generation_path in _list_generation_paths(path):
        generation = int(
            generation_path.stem.split("-", 1)[1]
        )
        card = load_memory_card_generation(path, generation=generation)

        result.append(
            {
                "generation": generation,
                **deepcopy(card),
            }
        )

    return result


def save_memory_card_generation(
    path: str | Path,
    card: Mapping[str, Any],
    *,
    max_generations: int,
) -> dict[str, Any]:
    """Persist a new verified generation with bounded retention."""

    if (
        type(max_generations) is not int
        or isinstance(max_generations, bool)
        or max_generations <= 0
    ):
        raise MemoryCardGenerationError(
            "max_generations must be a positive integer"
        )

    from .memory_card import verify_memory_card

    verify_memory_card(card)
    validated = deepcopy(dict(card))

    directory = _generation_dir(path)
    directory.mkdir(parents=True, exist_ok=True)

    existing = _list_generation_paths(path)
    next_generation = (
int(existing[-1].stem.split("-", 1)[1]) + 1
        if existing
        else 1
    )

    target = _generation_path(path, next_generation)
    saved = save_memory_card(target, validated)

    existing = _list_generation_paths(path)
    while len(existing) > max_generations:
        oldest = existing.pop(0)
        try:
            oldest.unlink()
        except OSError as exc:
            raise MemoryCardGenerationError(
                f"unable to remove retired generation: {oldest}"
            ) from exc

    return {
        "generation": next_generation,
        **deepcopy(saved),
    }

def load_memory_card_generation(
    path: str | Path,
    *,
    generation: int,
) -> dict[str, Any]:
    """Load one verified recorded-state generation."""

    if (
        type(generation) is not int
        or isinstance(generation, bool)
        or generation <= 0
    ):
        raise MemoryCardGenerationError(
            "generation must be a positive integer"
        )

    target = _generation_path(path, generation)

    if not target.exists():
        raise MemoryCardGenerationError(
            f"generation does not exist: {generation}"
        )

    try:
        card = load_memory_card(target)
    except MemoryCardError as exc:
        raise MemoryCardGenerationError(
            f"generation failed memory-card validation: {generation}"
        ) from exc

    return deepcopy(card)
