"""Tests for the Socratic CLI module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest


class TestConsole:
    """Tests for Console class."""

    def test_create_console(self):
        """Test creating a console."""
        from empathy_os.socratic.cli import Console

        console = Console()
        assert console is not None

    def test_console_use_color_default(self):
        """Test Console color default behavior."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=True)
        # use_color is True only if stdout.isatty() is True
        assert console is not None

    def test_console_no_color(self):
        """Test Console with color disabled."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        assert console.use_color is False

    def test_console_header(self, capsys):
        """Test Console header method."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        console.header("Test Header")

        captured = capsys.readouterr()
        assert "Test Header" in captured.out
        assert "=" in captured.out

    def test_console_subheader(self, capsys):
        """Test Console subheader method."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        console.subheader("Test Subheader")

        captured = capsys.readouterr()
        assert "Test Subheader" in captured.out

    def test_console_error(self, capsys):
        """Test console error output."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        console.error("An error occurred")

        captured = capsys.readouterr()
        assert "error" in captured.out.lower() or "An error" in captured.out

    def test_console_info(self, capsys):
        """Test console info output."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        console.info("Information message")

        captured = capsys.readouterr()
        assert "Information" in captured.out

    def test_console_success(self, capsys):
        """Test console success output."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        console.success("Operation completed")

        captured = capsys.readouterr()
        assert "Operation completed" in captured.out

    def test_console_warning(self, capsys):
        """Test console warning output."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        console.warning("Warning message")

        captured = capsys.readouterr()
        assert "Warning message" in captured.out

    def test_console_dim(self, capsys):
        """Test console dim output."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        console.dim("Dimmed text")

        captured = capsys.readouterr()
        assert "Dimmed text" in captured.out

    def test_console_progress_bar(self):
        """Test Console progress bar generation."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)

        # Test 50% progress
        bar = console.progress(0.5, width=20)
        assert "50%" in bar
        assert "[" in bar and "]" in bar

    def test_console_progress_full(self):
        """Test Console progress bar at 100%."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        bar = console.progress(1.0, width=10)
        assert "100%" in bar

    def test_console_progress_empty(self):
        """Test Console progress bar at 0%."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        bar = console.progress(0.0, width=10)
        assert "0%" in bar

    def test_console_table(self, capsys):
        """Test Console table output."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        headers = ["Name", "Age", "City"]
        rows = [
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"],
        ]
        console.table(headers, rows)

        captured = capsys.readouterr()
        assert "Name" in captured.out
        assert "Alice" in captured.out
        assert "Bob" in captured.out
        assert "-" in captured.out  # Separator line

    def test_console_table_empty(self, capsys):
        """Test Console table with no rows."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        headers = ["Name", "Age"]
        rows = []
        console.table(headers, rows)

        captured = capsys.readouterr()
        assert "Name" in captured.out
        assert "Age" in captured.out

    def test_console_colors_dict_exists(self):
        """Test that Console has COLORS dictionary."""
        from empathy_os.socratic.cli import Console

        assert hasattr(Console, "COLORS")
        assert "reset" in Console.COLORS
        assert "bold" in Console.COLORS
        assert "red" in Console.COLORS
        assert "green" in Console.COLORS
        assert "yellow" in Console.COLORS
        assert "blue" in Console.COLORS

    def test_console_color_function_disabled(self):
        """Test Console _c function with color disabled."""
        from empathy_os.socratic.cli import Console

        console = Console(use_color=False)
        result = console._c("red", "test text")
        assert result == "test text"  # No color codes


class TestGlobalConsole:
    """Tests for the global console instance."""

    def test_global_console_exists(self):
        """Test that global console instance exists."""
        from empathy_os.socratic.cli import console

        assert console is not None

    def test_global_console_is_console_instance(self):
        """Test that global console is a Console instance."""
        from empathy_os.socratic.cli import Console, console

        assert isinstance(console, Console)


class TestCLIParser:
    """Tests for CLI argument parser."""

    def test_create_parser(self):
        """Test argument parser creation."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        assert parser is not None
        assert parser.prog == "empathy socratic"

    def test_parser_start_command(self):
        """Test start command parsing."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["start", "--goal", "Test goal"])

        assert args.command == "start"
        assert args.goal == "Test goal"

    def test_parser_start_non_interactive(self):
        """Test start command with non-interactive flag."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["start", "--non-interactive"])

        assert args.command == "start"
        assert args.non_interactive is True

    def test_parser_resume_command(self):
        """Test resume command parsing."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["resume", "session-123"])

        assert args.command == "resume"
        assert args.session_id == "session-123"

    def test_parser_list_command(self):
        """Test list command parsing."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["list", "--state", "completed", "--limit", "10"])

        assert args.command == "list"
        assert args.state == "completed"
        assert args.limit == 10

    def test_parser_list_default_limit(self):
        """Test list command with default limit."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["list"])

        assert args.command == "list"
        assert args.limit == 20  # default

    def test_parser_blueprints_command(self):
        """Test blueprints command parsing."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["blueprints", "--domain", "security"])

        assert args.command == "blueprints"
        assert args.domain == "security"

    def test_parser_show_command(self):
        """Test show command parsing."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["show", "session-or-blueprint-id"])

        assert args.command == "show"
        assert args.id == "session-or-blueprint-id"

    def test_parser_delete_command(self):
        """Test delete command parsing."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["delete", "session-id", "--force"])

        assert args.command == "delete"
        assert args.session_id == "session-id"
        assert args.force is True

    def test_parser_delete_without_force(self):
        """Test delete command without force flag."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["delete", "session-id"])

        assert args.command == "delete"
        assert args.force is False

    def test_parser_export_command(self):
        """Test export command parsing."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["export", "blueprint-id", "--output", "output.json"])

        assert args.command == "export"
        assert args.blueprint_id == "blueprint-id"
        assert args.output == "output.json"

    def test_parser_no_command(self):
        """Test parser with no command."""
        from empathy_os.socratic.cli import create_parser

        parser = create_parser()
        args = parser.parse_args([])

        assert args.command is None


class TestCLIMain:
    """Tests for CLI main function."""

    def test_main_no_command(self):
        """Test main with no command returns 0."""
        from empathy_os.socratic.cli import main

        result = main([])
        assert result == 0

    def test_main_with_invalid_state(self, capsys):
        """Test main with invalid list state raises SystemExit."""
        from empathy_os.socratic.cli import main

        with patch("empathy_os.socratic.cli.get_default_storage") as mock_storage:
            mock_storage.return_value = MagicMock()

            # argparse catches invalid state and exits with code 2
            with pytest.raises(SystemExit) as exc_info:
                main(["list", "--state", "invalid_state"])

            assert exc_info.value.code == 2


class TestCLICommandList:
    """Tests for cmd_list function."""

    def test_cmd_list_empty(self, capsys):
        """Test cmd_list with no sessions."""
        from empathy_os.socratic.cli import cmd_list

        with patch("empathy_os.socratic.cli.get_default_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.list_sessions.return_value = []
            mock_get_storage.return_value = mock_storage

            args = argparse.Namespace(state=None, limit=20)
            result = cmd_list(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "No sessions found" in captured.out

    def test_cmd_list_with_sessions(self, capsys):
        """Test cmd_list with sessions."""
        from empathy_os.socratic.cli import cmd_list

        with patch("empathy_os.socratic.cli.get_default_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.list_sessions.return_value = [
                {
                    "session_id": "session-001",
                    "state": "completed",
                    "goal": "Test goal",
                    "updated_at": "2026-01-22T10:00:00",
                }
            ]
            mock_get_storage.return_value = mock_storage

            args = argparse.Namespace(state=None, limit=20)
            result = cmd_list(args)

            assert result == 0
            captured = capsys.readouterr()
            # Table output truncates IDs, check for session prefix and goal
            assert "session-" in captured.out
            assert "Test goal" in captured.out


class TestCLICommandBlueprints:
    """Tests for cmd_blueprints function."""

    def test_cmd_blueprints_empty(self, capsys):
        """Test cmd_blueprints with no blueprints."""
        from empathy_os.socratic.cli import cmd_blueprints

        with patch("empathy_os.socratic.cli.get_default_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.list_blueprints.return_value = []
            mock_get_storage.return_value = mock_storage

            args = argparse.Namespace(domain=None, limit=20)
            result = cmd_blueprints(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "No blueprints found" in captured.out


class TestCLICommandShow:
    """Tests for cmd_show function."""

    def test_cmd_show_not_found(self, capsys):
        """Test cmd_show with non-existent ID."""
        from empathy_os.socratic.cli import cmd_show

        with patch("empathy_os.socratic.cli.get_default_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.load_session.return_value = None
            mock_storage.load_blueprint.return_value = None
            mock_get_storage.return_value = mock_storage

            args = argparse.Namespace(id="nonexistent-id")
            result = cmd_show(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "Not found" in captured.out


class TestCLICommandDelete:
    """Tests for cmd_delete function."""

    def test_cmd_delete_not_found(self, capsys):
        """Test cmd_delete with non-existent session."""
        from empathy_os.socratic.cli import cmd_delete

        with patch("empathy_os.socratic.cli.get_default_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.delete_session.return_value = False
            mock_get_storage.return_value = mock_storage

            args = argparse.Namespace(session_id="nonexistent", force=True)
            result = cmd_delete(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.out

    def test_cmd_delete_success(self, capsys):
        """Test cmd_delete with existing session."""
        from empathy_os.socratic.cli import cmd_delete

        with patch("empathy_os.socratic.cli.get_default_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.delete_session.return_value = True
            mock_get_storage.return_value = mock_storage

            args = argparse.Namespace(session_id="session-001", force=True)
            result = cmd_delete(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "Deleted" in captured.out


class TestCLICommandExport:
    """Tests for cmd_export function."""

    def test_cmd_export_not_found(self, capsys):
        """Test cmd_export with non-existent blueprint."""
        from empathy_os.socratic.cli import cmd_export

        with patch("empathy_os.socratic.cli.get_default_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.load_blueprint.return_value = None
            mock_get_storage.return_value = mock_storage

            args = argparse.Namespace(blueprint_id="nonexistent", output=None)
            result = cmd_export(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.out


class TestFormRendering:
    """Tests for form rendering functions."""

    def test_render_form_interactive_exists(self):
        """Test that render_form_interactive function exists."""
        from empathy_os.socratic.cli import render_form_interactive

        assert callable(render_form_interactive)


class TestInputHelpers:
    """Tests for input helper functions."""

    def test_input_single_select_exists(self):
        """Test _input_single_select exists."""
        from empathy_os.socratic.cli import _input_single_select

        assert callable(_input_single_select)

    def test_input_multi_select_exists(self):
        """Test _input_multi_select exists."""
        from empathy_os.socratic.cli import _input_multi_select

        assert callable(_input_multi_select)

    def test_input_boolean_exists(self):
        """Test _input_boolean exists."""
        from empathy_os.socratic.cli import _input_boolean

        assert callable(_input_boolean)

    def test_input_text_exists(self):
        """Test _input_text exists."""
        from empathy_os.socratic.cli import _input_text

        assert callable(_input_text)

    def test_input_text_area_exists(self):
        """Test _input_text_area exists."""
        from empathy_os.socratic.cli import _input_text_area

        assert callable(_input_text_area)
