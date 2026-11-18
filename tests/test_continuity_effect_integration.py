
"""Subprocess-level continuity effect observation experiments."""

import subprocess
import sys

from holosim.continuity_effect_observation import evaluate_continuity_effect


def test_forged_block_with_real_effect(tmp_path):
    target = tmp_path / "effect.txt"

    candidate = (
        "from pathlib import Path; "
        "import sys; "
        "Path(sys.argv[1]).write_text('effect', encoding='utf-8'); "
        "print('BLOCK')"
    )

    completed = subprocess.run(
        [sys.executable, "-c", candidate, str(target)],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    # The report originates from the candidate.
    reported_decision = completed.stdout.strip()

    # The witness observes filesystem state after process termination.
    effect_observed = (
        target.is_file()
        and target.read_text(encoding="utf-8") == "effect"
    )

    result = evaluate_continuity_effect(
        reported_decision=reported_decision,
        action_attempted=True,
        effect_observed=effect_observed,
    )

    assert reported_decision == "BLOCK"
    assert effect_observed is True
    assert result["classification"] == "REPORTED_BLOCK_EFFECT_CONTRADICTION"
    assert result["accepted"] is False
    assert result["execution_authority"] == "NONE"
