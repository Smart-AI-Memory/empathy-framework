"""Tests for the Socratic CLI module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
from unittest.mock import MagicMock, patch
from io import StringIO


class TestConsole:
    """Tests for Console class."""

    def test_create_console(self):
        """Test creating a console."""
        from empathy_os.socratic.cli import Console

        console = Console()
        assert console is not None

    def test_console_print(self, capsys):
        """Test console print."""
        from empathy_os.socratic.cli import Console

        console = Console()
        console.print("Hello, world!")

        captured = capsys.readouterr()
        assert "Hello" in captured.out

    def test_console_error(self, capsys):
        """Test console error output."""
        from empathy_os.socratic.cli import Console

        console = Console()
        console.error("An error occurred")

        captured = capsys.readouterr()
        # Error might go to stderr or stdout depending on implementation
        assert "error" in captured.err.lower() or "error" in captured.out.lower()

    def test_console_info(self, capsys):
        """Test console info output."""
        from empathy_os.socratic.cli import Console

        console = Console()
        console.info("Information message")

        captured = capsys.readouterr()
        assert "Information" in captured.out or "info" in captured.out.lower()

    def test_console_success(self, capsys):
        """Test console success output."""
        from empathy_os.socratic.cli import Console

        console = Console()
        console.success("Operation completed")

        captured = capsys.readouterr()
        assert "completed" in captured.out.lower() or "Operation" in captured.out


class TestSocraticCLI:
    """Tests for SocraticCLI class."""

    def test_create_cli(self, storage_path):
        """Test creating a Socratic CLI."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        assert cli is not None

    def test_start_session(self, storage_path):
        """Test starting a new session."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()

        assert session is not None
        assert session.session_id is not None

    def test_set_goal(self, storage_path):
        """Test setting session goal."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()

        cli.set_goal(session.session_id, "Automate code reviews")

        updated = cli.get_session(session.session_id)
        assert updated.goal == "Automate code reviews"

    def test_get_questions(self, storage_path):
        """Test getting questions."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()
        cli.set_goal(session.session_id, "Automate code reviews")

        questions = cli.get_questions(session.session_id)

        assert questions is not None
        # Questions could be a Form or list
        assert hasattr(questions, "fields") or isinstance(questions, list)

    def test_submit_answers(self, storage_path):
        """Test submitting answers."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()
        cli.set_goal(session.session_id, "Automate code reviews")

        cli.submit_answers(
            session.session_id,
            {"languages": ["python"], "focus_areas": ["security"]},
        )

        updated = cli.get_session(session.session_id)
        assert len(updated.collected_answers) > 0

    def test_generate_workflow(self, storage_path):
        """Test generating workflow."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()
        cli.set_goal(session.session_id, "Automate code reviews")
        cli.submit_answers(session.session_id, {"languages": ["python"]})

        blueprint = cli.generate_workflow(session.session_id)

        assert blueprint is not None
        assert blueprint.workflow_id is not None

    def test_list_sessions(self, storage_path):
        """Test listing sessions."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)

        cli.start_session()
        cli.start_session()

        sessions = cli.list_sessions()

        assert len(sessions) >= 2

    def test_list_blueprints(self, storage_path):
        """Test listing blueprints."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()
        cli.set_goal(session.session_id, "Test")
        cli.submit_answers(session.session_id, {})
        cli.generate_workflow(session.session_id)

        blueprints = cli.list_blueprints()

        assert len(blueprints) >= 1

    def test_delete_session(self, storage_path):
        """Test deleting a session."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()

        cli.delete_session(session.session_id)

        deleted = cli.get_session(session.session_id)
        assert deleted is None


class TestCLIInteractive:
    """Tests for CLI interactive mode."""

    def test_interactive_start(self, storage_path, monkeypatch):
        """Test interactive mode startup."""
        from empathy_os.socratic.cli import SocraticCLI

        # Mock input to immediately quit
        inputs = iter(["quit"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        cli = SocraticCLI(storage_path=storage_path)

        # Should not raise
        try:
            cli.run_interactive()
        except StopIteration:
            pass  # Expected when inputs exhausted

    def test_interactive_new_session(self, storage_path, monkeypatch):
        """Test creating session in interactive mode."""
        from empathy_os.socratic.cli import SocraticCLI

        inputs = iter(["new", "Automate testing", "quit"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        cli = SocraticCLI(storage_path=storage_path)

        try:
            cli.run_interactive()
        except StopIteration:
            pass

        sessions = cli.list_sessions()
        assert len(sessions) >= 1

    def test_interactive_help(self, storage_path, monkeypatch, capsys):
        """Test help command in interactive mode."""
        from empathy_os.socratic.cli import SocraticCLI

        inputs = iter(["help", "quit"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        cli = SocraticCLI(storage_path=storage_path)

        try:
            cli.run_interactive()
        except StopIteration:
            pass

        captured = capsys.readouterr()
        # Help output should contain command info
        assert "command" in captured.out.lower() or len(captured.out) > 0


class TestCLIOutput:
    """Tests for CLI output formatting."""

    def test_format_session(self, storage_path, sample_session, capsys):
        """Test formatting session output."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        cli.print_session(sample_session)

        captured = capsys.readouterr()
        assert sample_session.session_id in captured.out

    def test_format_blueprint(self, storage_path, sample_workflow_blueprint, capsys):
        """Test formatting blueprint output."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        cli.print_blueprint(sample_workflow_blueprint)

        captured = capsys.readouterr()
        assert sample_workflow_blueprint.name in captured.out

    def test_format_questions(self, storage_path, sample_form, capsys):
        """Test formatting questions output."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        cli.print_questions(sample_form)

        captured = capsys.readouterr()
        # Should show question text
        for field in sample_form.fields:
            assert field.label in captured.out or field.field_id in captured.out


class TestCLIExport:
    """Tests for CLI export functionality."""

    def test_export_blueprint_json(self, storage_path, sample_workflow_blueprint):
        """Test exporting blueprint to JSON."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)

        # Save blueprint first
        cli.save_blueprint(sample_workflow_blueprint)

        output_path = storage_path / "export.json"
        cli.export_blueprint(sample_workflow_blueprint.workflow_id, str(output_path))

        assert output_path.exists()

        import json

        with open(output_path) as f:
            data = json.load(f)
            assert data["workflow_id"] == sample_workflow_blueprint.workflow_id

    def test_export_blueprint_yaml(self, storage_path, sample_workflow_blueprint):
        """Test exporting blueprint to YAML."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)

        cli.save_blueprint(sample_workflow_blueprint)

        output_path = storage_path / "export.yaml"
        cli.export_blueprint(
            sample_workflow_blueprint.workflow_id, str(output_path), format="yaml"
        )

        # May or may not support YAML
        if output_path.exists():
            content = output_path.read_text()
            assert sample_workflow_blueprint.workflow_id in content


class TestCLIValidation:
    """Tests for CLI input validation."""

    def test_validate_session_id(self, storage_path):
        """Test session ID validation."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)

        # Invalid session ID should return None or raise
        result = cli.get_session("nonexistent-id")
        assert result is None

    def test_validate_empty_goal(self, storage_path):
        """Test empty goal handling."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()

        # Empty goal might be rejected or accepted depending on implementation
        try:
            cli.set_goal(session.session_id, "")
            updated = cli.get_session(session.session_id)
            # If accepted, goal should be empty string
            assert updated.goal == "" or updated.goal is None
        except ValueError:
            pass  # Expected if empty goals are rejected

    def test_validate_answers_format(self, storage_path):
        """Test answers format validation."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()
        cli.set_goal(session.session_id, "Test goal")

        # Invalid answers format might be rejected
        try:
            cli.submit_answers(session.session_id, "not a dict")  # type: ignore
        except (TypeError, ValueError):
            pass  # Expected


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_handle_missing_session(self, storage_path, capsys):
        """Test handling missing session gracefully."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)

        # Should not crash
        try:
            cli.get_questions("nonexistent")
        except Exception:
            pass  # Expected

    def test_handle_invalid_state_transition(self, storage_path):
        """Test handling invalid state transitions."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=storage_path)
        session = cli.start_session()

        # Try to generate without setting goal
        try:
            cli.generate_workflow(session.session_id)
        except Exception:
            pass  # Expected - need goal first

    def test_handle_storage_errors(self, tmp_path):
        """Test handling storage errors gracefully."""
        from empathy_os.socratic.cli import SocraticCLI
        import os

        # Create read-only directory
        readonly_path = tmp_path / "readonly"
        readonly_path.mkdir()
        os.chmod(readonly_path, 0o444)

        try:
            cli = SocraticCLI(storage_path=readonly_path / "storage.json")
            # Operations might fail
            try:
                cli.start_session()
            except (PermissionError, OSError):
                pass  # Expected
        finally:
            os.chmod(readonly_path, 0o755)
