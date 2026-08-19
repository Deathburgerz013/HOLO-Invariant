"""Deterministic generated README status boundary."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path
from typing import Any, Sequence


START_MARKER = "<!-- HOLO:STATUS:START -->"
END_MARKER = "<!-- HOLO:STATUS:END -->"

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(
            f"Required repository file is missing: {path}"
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError(
            f"Required repository file cannot be read: {path}"
        ) from exc


def _project_version(pyproject_path: Path) -> str:
    source = _read_text(pyproject_path)

    project_match = re.search(
        (
            r"(?ms)^\[project\]\s*$"
            r"(?P<body>.*?)"
            r"(?=^\[|\Z)"
        ),
        source,
    )
    if project_match is None:
        raise ValueError(
            "pyproject.toml has no [project] section"
        )

    version_match = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"\s*$',
        project_match.group("body"),
    )
    if version_match is None:
        raise ValueError(
            "pyproject.toml has no project version"
        )

    return version_match.group(1)


def _literal_string(
    node: ast.AST,
) -> str | None:
    if (
        isinstance(node, ast.Constant)
        and type(node.value) is str
    ):
        return node.value
    return None


def _cli_commands(cli_path: Path) -> list[str]:
    source = _read_text(cli_path)

    try:
        tree = ast.parse(
            source,
            filename=str(cli_path),
        )
    except SyntaxError as exc:
        raise ValueError(
            "Holo CLI source is not valid Python"
        ) from exc

    commands: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        function = node.func
        if not (
            isinstance(function, ast.Attribute)
            and function.attr == "add_parser"
            and node.args
        ):
            continue

        command = _literal_string(node.args[0])
        if command is not None:
            commands.add(command)

    if not commands:
        raise ValueError(
            "No public CLI commands were discovered"
        )

    return sorted(commands)


def _decorator_name(
    decorator: ast.AST,
) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None

    function = decorator.func
    if not isinstance(function, ast.Attribute):
        return None

    return function.attr


def _mcp_surfaces(
    adapter_path: Path,
) -> tuple[list[str], list[str]]:
    source = _read_text(adapter_path)

    try:
        tree = ast.parse(
            source,
            filename=str(adapter_path),
        )
    except SyntaxError as exc:
        raise ValueError(
            "MCP adapter source is not valid Python"
        ) from exc

    tools: set[str] = set()
    resources: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        for decorator in node.decorator_list:
            decorator_name = _decorator_name(
                decorator
            )

            if decorator_name == "tool":
                tools.add(node.name)
                continue

            if decorator_name != "resource":
                continue

            assert isinstance(decorator, ast.Call)

            if not decorator.args:
                raise ValueError(
                    "MCP resource decorator has no URI"
                )

            uri = _literal_string(
                decorator.args[0]
            )
            if uri is None:
                raise ValueError(
                    "MCP resource URI must be literal"
                )

            resources.add(uri)

    if not tools:
        raise ValueError(
            "No public MCP tools were discovered"
        )

    if not resources:
        raise ValueError(
            "No public MCP resources were discovered"
        )

    return (
        sorted(tools),
        sorted(resources),
    )


def _public_schemas(
    schema_directory: Path,
) -> list[str]:
    if not schema_directory.is_dir():
        raise ValueError(
            "Public schema directory is missing"
        )

    schemas = sorted(
        path.name
        for path in schema_directory.glob(
            "*.schema.json"
        )
        if path.is_file()
    )

    if not schemas:
        raise ValueError(
            "No public schemas were discovered"
        )

    return schemas


def collect_repository_status(
    root: Path | str = PROJECT_ROOT,
) -> dict[str, Any]:
    """Collect public status from repository sources."""
    repository_root = Path(root).resolve()

    mcp_tools, mcp_resources = _mcp_surfaces(
        repository_root
        / "holosim"
        / "mcp_adapter.py"
    )

    return {
        "version": _project_version(
            repository_root
            / "pyproject.toml"
        ),
        "cli_commands": _cli_commands(
            repository_root
            / "holosim"
            / "holo_cli.py"
        ),
        "schemas": _public_schemas(
            repository_root
            / "schemas"
        ),
        "mcp_tools": mcp_tools,
        "mcp_resources": mcp_resources,
    }


def _inline_code_list(
    values: Sequence[str],
) -> str:
    return ", ".join(
        f"`{value}`"
        for value in values
    )


def render_status_section(
    status: dict[str, Any],
) -> str:
    """Render the bounded generated README section."""
    version = status["version"]
    cli_commands = status["cli_commands"]
    schemas = status["schemas"]
    mcp_tools = status["mcp_tools"]
    mcp_resources = status["mcp_resources"]

    lines = [
        START_MARKER,
        "## Generated public status",
        "",
        (
            "<!-- Generated by "
            "python -m holosim.readme_status --write. "
            "Do not edit inside this boundary. -->"
        ),
        "",
        "| Surface | Current repository state |",
        "|---|---:|",
        f"| Package version | `{version}` |",
        f"| CLI commands | {len(cli_commands)} |",
        f"| Public schemas | {len(schemas)} |",
        f"| MCP tools | {len(mcp_tools)} |",
        f"| MCP resources | {len(mcp_resources)} |",
        "",
        "**CLI:** "
        + _inline_code_list(cli_commands),
        "",
        "**Schemas:** "
        + _inline_code_list(schemas),
        "",
        "**MCP tools:** "
        + _inline_code_list(mcp_tools),
        "",
        "**MCP resources:** "
        + _inline_code_list(mcp_resources),
        END_MARKER,
    ]

    return "\n".join(lines)


def replace_status_section(
    readme: str,
    generated: str,
) -> str:
    """Replace exactly one generated README boundary."""
    start_count = readme.count(START_MARKER)
    end_count = readme.count(END_MARKER)

    if (
        start_count != 1
        or end_count != 1
    ):
        raise ValueError(
            "README status boundary must contain "
            "exactly one start and one end marker"
        )

    start = readme.index(START_MARKER)
    end = (
        readme.index(END_MARKER)
        + len(END_MARKER)
    )

    if start >= end:
        raise ValueError(
            "README status boundary is invalid"
        )

    return (
        readme[:start]
        + generated
        + readme[end:]
    )


def expected_readme(
    root: Path | str = PROJECT_ROOT,
) -> str:
    """Return README content with current status."""
    repository_root = Path(root).resolve()
    readme_path = repository_root / "README.md"

    readme = _read_text(readme_path)
    status = collect_repository_status(
        repository_root
    )
    generated = render_status_section(status)

    return replace_status_section(
        readme,
        generated,
    )


def check_readme(
    root: Path | str = PROJECT_ROOT,
) -> bool:
    """Return whether README status is current."""
    repository_root = Path(root).resolve()
    readme_path = repository_root / "README.md"

    current = _read_text(readme_path)
    expected = expected_readme(
        repository_root
    )

    return current == expected


def write_readme(
    root: Path | str = PROJECT_ROOT,
) -> bool:
    """Update only the generated README boundary."""
    repository_root = Path(root).resolve()
    readme_path = repository_root / "README.md"

    current = _read_text(readme_path)
    updated = expected_readme(
        repository_root
    )

    if current == updated:
        return False

    readme_path.write_text(
        updated,
        encoding="utf-8",
    )
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check or update the generated "
            "HOLO README status boundary"
        )
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help=(
            "Fail when the generated README "
            "status is stale"
        ),
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help=(
            "Update only the generated README "
            "status boundary"
        ),
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository root",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.check:
            if check_readme(args.root):
                print(
                    "README generated status is current."
                )
                return 0

            print(
                "README generated status is stale. "
                "Run: python -m "
                "holosim.readme_status --write"
            )
            return 1

        changed = write_readme(args.root)
    except ValueError as exc:
        print(f"README status error: {exc}")
        return 2
    except (OSError, UnicodeError) as exc:
        print(f"README status error: {exc}")
        return 2

    if changed:
        print(
            "README generated status updated."
        )
    else:
        print(
            "README generated status already current."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())