from __future__ import annotations

from holosim.convergence_renderer import render_convergence_html


def test_renderer_exposes_convergence_differences_as_html() -> None:
    observed = {
        "goal": "add must return the sum",
        "status": "CONVERGED",
        "terminal_reason": "NO_RELEVANT_DIFFERENCE",
        "iteration_count": 2,
        "correction_count": 1,
        "receipt_hash": "run-hash-1",
        "iterations": [
            {
                "number": 1,
                "status": "CORRECTED",
                "difference_present": True,
                "difference": "Fix add so it returns the sum",
                "builder_invoked": True,
                "builder_receipt_hash": "build-hash-1",
                "verification_passed": True,
            },
            {
                "number": 2,
                "status": "CONVERGED",
                "difference_present": False,
                "difference": "NO_RELEVANT_DIFFERENCE",
                "builder_invoked": False,
                "builder_receipt_hash": None,
                "verification_passed": None,
            },
        ],
    }

    html = render_convergence_html(observed)

    assert "<!doctype html>" in html
    assert "add must return the sum" in html
    assert "CONVERGED" in html
    assert "Fix add so it returns the sum" in html
    assert "NO_RELEVANT_DIFFERENCE" in html
    assert "Iteration 1" in html
    assert "Iteration 2" in html
    assert "run-hash-1" in html


def test_renderer_escapes_untrusted_values() -> None:
    observed = {
        "goal": "<script>alert('bad')</script>",
        "status": "STOPPED",
        "terminal_reason": "FAILED",
        "iteration_count": 0,
        "correction_count": 0,
        "receipt_hash": "hash",
        "iterations": [],
    }

    html = render_convergence_html(observed)

    assert "<script>alert('bad')</script>" not in html
    assert "&lt;script&gt;" in html
def test_renderer_provides_opt_in_semantic_audio() -> None:
    observed = {
        "goal": "preserve continuity",
        "status": "CONVERGED",
        "terminal_reason": "NO_RELEVANT_DIFFERENCE",
        "iteration_count": 2,
        "correction_count": 1,
        "receipt_hash": "run-hash-audio",
        "iterations": [
            {
                "number": 1,
                "status": "CORRECTED",
                "difference_present": True,
                "difference": "Repair continuity relation",
                "builder_invoked": True,
                "builder_receipt_hash": "build-hash-audio",
                "verification_passed": True,
            },
            {
                "number": 2,
                "status": "CONVERGED",
                "difference_present": False,
                "difference": "NO_RELEVANT_DIFFERENCE",
                "builder_invoked": False,
                "builder_receipt_hash": None,
                "verification_passed": None,
            },
        ],
    }

    html = render_convergence_html(observed)

    assert 'id="sound-toggle"' in html
    assert "Enable sound" in html
    assert 'data-status="CORRECTED"' in html
    assert 'data-status="CONVERGED"' in html
    assert "AudioContext" in html
    assert "createOscillator" in html
    assert "createGain" in html

    # Sound must require human interaction. Browsers enforce this anyway,
    # because apparently even cosmic sorrow needs a consent button.
    assert "<audio autoplay" not in html