"""Code inspection commands.

Commands for scanning and inspecting codebases for issues.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import subprocess
from pathlib import Path

from empathy_os.cli.core import console


def scan(
    path: Path = Path("."),
    format_out: str = "text",
    fix: bool = False,
    staged: bool = False,
) -> None:
    """Scan codebase for issues."""
    args = ["empathy-scan", str(path)]
    if format_out != "text":
        args.extend(["--format", format_out])
    if fix:
        args.append("--fix")
    if staged:
        args.append("--staged")

    result = subprocess.run(args, check=False, capture_output=False)
    if result.returncode != 0:
        console.print("[yellow]Note: empathy-scan may not be installed[/yellow]")
        console.print("Install with: pip install empathy-framework[software]")


def inspect_cmd(
    path: Path = Path("."),
    format_out: str = "text",
) -> None:
    """Deep inspection with code analysis."""
    args = ["empathy-inspect", str(path)]
    if format_out != "text":
        args.extend(["--format", format_out])

    result = subprocess.run(args, check=False, capture_output=False)
    if result.returncode != 0:
        console.print("[yellow]Note: empathy-inspect may not be installed[/yellow]")
        console.print("Install with: pip install empathy-framework[software]")
