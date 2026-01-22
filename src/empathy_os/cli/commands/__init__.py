"""CLI command modules for Empathy Framework.

Each module contains a Typer app that can be registered with the main app.
"""

from empathy_os.cli.commands import inspection, memory, provider, utilities

__all__ = ["memory", "provider", "inspection", "utilities"]
