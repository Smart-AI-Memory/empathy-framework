"""Entry point for python -m empathy_os.cli.

This redirects to the legacy cli.py module for backward compatibility.
The cli/ package coexists with cli.py, but Python finds packages first.
"""

import sys
from pathlib import Path

# Add the parent directory to find the cli.py module
parent = Path(__file__).parent.parent
if str(parent) not in sys.path:
    sys.path.insert(0, str(parent))

# Import and run the legacy CLI
# We can't import cli directly because of the package name conflict
# So we use importlib to load cli.py as a module
import importlib.util

cli_py_path = parent / "cli.py"
spec = importlib.util.spec_from_file_location("cli_legacy", cli_py_path)
cli_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli_module)

if __name__ == "__main__":
    cli_module.main()
