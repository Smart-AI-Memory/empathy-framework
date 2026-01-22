"""TDD-First methodology for wizard creation.

Write tests first, then implement wizard.

Workflow:
1. Generate comprehensive tests based on patterns
2. Run tests (they should all fail)
3. Generate minimal wizard skeleton
4. Implement wizard to make tests pass

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import logging
from pathlib import Path

from test_generator import TestGenerator

from empathy_os.config import _validate_file_path

logger = logging.getLogger(__name__)


class TDDFirst:
    """TDD-First methodology: Write tests first, implement wizard.

    Benefits:
    - Better test coverage (tests written before code)
    - Clear specification (tests define behavior)
    - Prevents over-engineering (only code what's tested)
    """

    def __init__(self):
        """Initialize TDD-First methodology."""
        self.test_generator = TestGenerator()

    def create_wizard(
        self,
        name: str,
        domain: str,
        wizard_type: str,
        pattern_ids: list[str],
    ) -> dict:
        """Create wizard using TDD-First methodology.

        Args:
            name: Wizard name
            domain: Domain
            wizard_type: Wizard type
            pattern_ids: Pattern IDs to use

        Returns:
            Dictionary with files and next steps

        """
        logger.info(f"Creating wizard '{name}' using TDD-First methodology")

        # Step 1: Generate tests FIRST
        logger.info("Step 1: Generating tests...")
        tests = self.test_generator.generate_tests(
            wizard_id=name,
            pattern_ids=pattern_ids,
        )

        # Write test files
        test_dir = Path("tests/unit/wizards")
        test_dir.mkdir(parents=True, exist_ok=True)

        unit_test_file = test_dir / f"test_{name}_wizard.py"
        validated_unit_test = _validate_file_path(str(unit_test_file))
        with open(validated_unit_test, "w") as f:
            f.write(tests["unit"])

        fixtures_file = test_dir / f"fixtures_{name}.py"
        validated_fixtures = _validate_file_path(str(fixtures_file))
        with open(validated_fixtures, "w") as f:
            f.write(tests["fixtures"])

        # Step 2: Generate minimal wizard skeleton
        logger.info("Step 2: Generating minimal wizard skeleton...")
        wizard_file = self._generate_skeleton(name, wizard_type)

        logger.info(f"✓ Wizard '{name}' scaffolded with TDD-First methodology!")

        return {
            "files": [unit_test_file, fixtures_file, wizard_file],
            "next_steps": [
                f"1. Run tests (they should FAIL): pytest {unit_test_file}",
                "2. Read test failures to understand requirements",
                f"3. Implement wizard in {wizard_file} to make tests pass",
                "4. Run tests again until all pass",
                "5. Refactor while keeping tests green",
            ],
        }

    def _generate_skeleton(self, name: str, wizard_type: str) -> Path:
        """Generate minimal wizard skeleton.

        Args:
            name: Wizard name
            wizard_type: Wizard type

        Returns:
            Path to skeleton file

        """
        class_name = "".join(part.capitalize() for part in name.split("_")) + "Wizard"

        skeleton = f'''"""
{class_name} - Minimal skeleton for TDD.

Implement methods to make tests pass.
"""


class {class_name}:
    """Wizard for {name}."""

    def __init__(self):
        """Initialize wizard."""
        pass

    async def process(self, **kwargs):
        """Process wizard request.

        TODO: Implement to make tests pass.
        """
        raise NotImplementedError("Implement to make tests pass")
'''

        wizard_dir = Path("wizards" if wizard_type != "coach" else "coach_wizards")
        wizard_dir.mkdir(parents=True, exist_ok=True)

        wizard_file = wizard_dir / f"{name}_wizard.py"
        validated_wizard = _validate_file_path(str(wizard_file))
        with open(validated_wizard, "w") as f:
            f.write(skeleton)

        return validated_wizard
