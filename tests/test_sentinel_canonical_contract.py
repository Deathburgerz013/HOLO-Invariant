from pathlib import Path

import pytest

from holosim.canonical import CanonicalValueError
from holosim.sentinel import stable_hash


def test_sentinel_hash_rejects_values_outside_canonical_contract() -> None:
    with pytest.raises(CanonicalValueError):
        stable_hash({"path": Path("evidence.json")})
