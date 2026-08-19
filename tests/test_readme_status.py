from pathlib import Path

import pytest

from holosim.readme_status import (
    END_MARKER,
    START_MARKER,
    collect_repository_status,
    render_status_section,
    replace_status_section,
)


ROOT = Path(__file__).resolve().parents[1]


def test_repository_status_comes_from_public_surfaces():
    status = collect_repository_status(ROOT)

    assert status["version"] == "0.4.9"

    assert status["cli_commands"] == [
        "append",
        "check-spines",
        "demo",
        "doctor",
        "health",
        "idx-check",
        "index",
        "local-converge",
        "operator-summary",
        "replay",
        "resume",
        "review",
        "serve",
        "service-status",
        "test",
        "verify",
    ]

    assert status["schemas"] == [
        "idx-check-receipt.schema.json",
        "idx-spine-packet.schema.json",
    ]

    assert status["mcp_tools"] == [
        "idx_check",
    ]

    assert status["mcp_resources"] == [
        "holo://schemas/idx-check-receipt",
        "holo://schemas/idx-spine-packet",
    ]


def test_rendered_status_is_bounded_and_deterministic():
    status = collect_repository_status(ROOT)

    first = render_status_section(status)
    second = render_status_section(status)

    assert first == second
    assert first.startswith(START_MARKER)
    assert first.endswith(END_MARKER)

    assert "Package version | `0.4.9`" in first
    assert "CLI commands | 16" in first
    assert "Public schemas | 2" in first
    assert "MCP tools | 1" in first
    assert "MCP resources | 2" in first

    assert "`idx-check`" in first
    assert "`idx_check`" in first
    assert (
        "`holo://schemas/idx-spine-packet`"
        in first
    )


def test_replace_changes_only_generated_boundary():
    original = (
        "# HOLO-Invariant\n\n"
        "Human introduction.\n\n"
        f"{START_MARKER}\n"
        "stale generated material\n"
        f"{END_MARKER}\n\n"
        "Human conclusion.\n"
    )

    generated = (
        f"{START_MARKER}\n"
        "current generated material\n"
        f"{END_MARKER}"
    )

    updated = replace_status_section(
        original,
        generated,
    )

    assert updated == (
        "# HOLO-Invariant\n\n"
        "Human introduction.\n\n"
        f"{START_MARKER}\n"
        "current generated material\n"
        f"{END_MARKER}\n\n"
        "Human conclusion.\n"
    )


@pytest.mark.parametrize(
    "readme",
    [
        "# Missing both markers\n",
        f"# Missing end\n\n{START_MARKER}\n",
        f"# Missing start\n\n{END_MARKER}\n",
        (
            f"{START_MARKER}\n"
            f"{END_MARKER}\n"
            f"{START_MARKER}\n"
            f"{END_MARKER}\n"
        ),
    ],
)
def test_replace_fails_closed_on_invalid_boundary(
    readme: str,
):
    with pytest.raises(
        ValueError,
        match="README status boundary",
    ):
        replace_status_section(
            readme,
            (
                f"{START_MARKER}\n"
                "generated\n"
                f"{END_MARKER}"
            ),
        )