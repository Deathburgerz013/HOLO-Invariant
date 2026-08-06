from __future__ import annotations

import pytest

from holosim.bounded_transformation_engine import (
    replace_exact_once,
)


def test_replace_exact_once_rejects_noop_replacement():
    with pytest.raises(
        ValueError,
        match="replacement must change the matched fragment",
    ):
        replace_exact_once(
            "alpha\ntarget\nomega\n",
            expected="target",
            replacement="target",
        )