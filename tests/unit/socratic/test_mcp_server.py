"""Tests for the Socratic MCP server module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
import json


class TestSocraticMCPServer:
    """Tests for SocraticMCPServer class."""

    def test_create_server(self, storage_path):
        """Test creating an MCP server."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)
        assert server is not None

    def test_list_tools(self, storage_path):
        """Test listing available tools."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)
        tools = server.list_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0

        # Check tool structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_start_session_tool(self, storage_path):
        """Test socratic_start_session tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        result = server.call_tool("socratic_start_session", {})

        assert "session_id" in result
        assert "state" in result

    def test_set_goal_tool(self, storage_path):
        """Test socratic_set_goal tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        # First start a session
        session_result = server.call_tool("socratic_start_session", {})
        session_id = session_result["session_id"]

        # Set goal
        result = server.call_tool(
            "socratic_set_goal",
            {
                "session_id": session_id,
                "goal": "Automate code reviews for Python projects",
            },
        )

        assert result["session_id"] == session_id
        assert "awaiting" in result["state"].lower() or "goal" in str(result).lower()

    def test_get_questions_tool(self, storage_path):
        """Test socratic_get_questions tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        # Start session and set goal
        session_result = server.call_tool("socratic_start_session", {})
        session_id = session_result["session_id"]

        server.call_tool(
            "socratic_set_goal",
            {
                "session_id": session_id,
                "goal": "Automate code reviews",
            },
        )

        # Get questions
        result = server.call_tool(
            "socratic_get_questions",
            {"session_id": session_id},
        )

        assert "questions" in result or "form" in result or "fields" in result

    def test_submit_answers_tool(self, storage_path):
        """Test socratic_submit_answers tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        # Setup session
        session_result = server.call_tool("socratic_start_session", {})
        session_id = session_result["session_id"]

        server.call_tool(
            "socratic_set_goal",
            {
                "session_id": session_id,
                "goal": "Automate code reviews",
            },
        )

        # Submit answers
        result = server.call_tool(
            "socratic_submit_answers",
            {
                "session_id": session_id,
                "answers": {"languages": ["python"], "focus_areas": ["security"]},
            },
        )

        assert "session_id" in result

    def test_generate_workflow_tool(self, storage_path):
        """Test socratic_generate_workflow tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        # Full flow
        session_result = server.call_tool("socratic_start_session", {})
        session_id = session_result["session_id"]

        server.call_tool(
            "socratic_set_goal",
            {
                "session_id": session_id,
                "goal": "Automate code reviews",
            },
        )

        server.call_tool(
            "socratic_submit_answers",
            {
                "session_id": session_id,
                "answers": {"languages": ["python"]},
            },
        )

        # Generate workflow
        result = server.call_tool(
            "socratic_generate_workflow",
            {"session_id": session_id},
        )

        assert "workflow_id" in result or "blueprint" in result

    def test_list_sessions_tool(self, storage_path):
        """Test socratic_list_sessions tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        # Create some sessions
        server.call_tool("socratic_start_session", {})
        server.call_tool("socratic_start_session", {})

        result = server.call_tool("socratic_list_sessions", {})

        assert "sessions" in result
        assert len(result["sessions"]) >= 2

    def test_get_session_tool(self, storage_path):
        """Test socratic_get_session tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        # Create session
        session_result = server.call_tool("socratic_start_session", {})
        session_id = session_result["session_id"]

        # Get session
        result = server.call_tool(
            "socratic_get_session",
            {"session_id": session_id},
        )

        assert result["session_id"] == session_id

    def test_analyze_goal_tool(self, storage_path):
        """Test socratic_analyze_goal tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        result = server.call_tool(
            "socratic_analyze_goal",
            {"goal": "I want to scan code for security vulnerabilities"},
        )

        assert "analysis" in result or "domains" in result or "recommendations" in result

    def test_recommend_agents_tool(self, storage_path):
        """Test socratic_recommend_agents tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        result = server.call_tool(
            "socratic_recommend_agents",
            {
                "goal": "Generate tests for my API",
                "context": {"language": "python", "framework": "fastapi"},
            },
        )

        assert "recommendations" in result or "agents" in result

    def test_invalid_tool_call(self, storage_path):
        """Test calling non-existent tool."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        with pytest.raises(Exception):
            server.call_tool("non_existent_tool", {})

    def test_tool_with_invalid_session(self, storage_path):
        """Test tool with invalid session ID."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        with pytest.raises(Exception):
            server.call_tool(
                "socratic_get_session",
                {"session_id": "non-existent-id"},
            )


class TestSocraticTools:
    """Tests for SOCRATIC_TOOLS constant."""

    def test_tools_defined(self):
        """Test that SOCRATIC_TOOLS is defined."""
        from empathy_os.socratic.mcp_server import SOCRATIC_TOOLS

        assert SOCRATIC_TOOLS is not None
        assert isinstance(SOCRATIC_TOOLS, list)

    def test_tools_have_required_fields(self):
        """Test that all tools have required fields."""
        from empathy_os.socratic.mcp_server import SOCRATIC_TOOLS

        for tool in SOCRATIC_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_expected_tools_exist(self):
        """Test that expected tools exist."""
        from empathy_os.socratic.mcp_server import SOCRATIC_TOOLS

        tool_names = [t["name"] for t in SOCRATIC_TOOLS]

        expected = [
            "socratic_start_session",
            "socratic_set_goal",
            "socratic_get_questions",
            "socratic_submit_answers",
            "socratic_generate_workflow",
        ]

        for expected_tool in expected:
            assert expected_tool in tool_names, f"Missing tool: {expected_tool}"


class TestMCPServerAsync:
    """Tests for async MCP server methods."""

    @pytest.mark.asyncio
    async def test_async_call_tool(self, storage_path):
        """Test async tool call."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        if hasattr(server, "call_tool_async"):
            result = await server.call_tool_async("socratic_start_session", {})
            assert "session_id" in result

    @pytest.mark.asyncio
    async def test_async_list_tools(self, storage_path):
        """Test async list tools."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=storage_path)

        if hasattr(server, "list_tools_async"):
            tools = await server.list_tools_async()
            assert len(tools) > 0


class TestMCPToolSchemas:
    """Tests for MCP tool input schemas."""

    def test_start_session_schema(self):
        """Test socratic_start_session schema."""
        from empathy_os.socratic.mcp_server import SOCRATIC_TOOLS

        tool = next(t for t in SOCRATIC_TOOLS if t["name"] == "socratic_start_session")
        schema = tool["inputSchema"]

        assert schema["type"] == "object"
        # Should have no required fields
        assert "required" not in schema or len(schema.get("required", [])) == 0

    def test_set_goal_schema(self):
        """Test socratic_set_goal schema."""
        from empathy_os.socratic.mcp_server import SOCRATIC_TOOLS

        tool = next(t for t in SOCRATIC_TOOLS if t["name"] == "socratic_set_goal")
        schema = tool["inputSchema"]

        assert "session_id" in schema["properties"]
        assert "goal" in schema["properties"]
        assert "session_id" in schema.get("required", [])
        assert "goal" in schema.get("required", [])

    def test_schema_valid_json(self):
        """Test all schemas are valid JSON."""
        from empathy_os.socratic.mcp_server import SOCRATIC_TOOLS

        for tool in SOCRATIC_TOOLS:
            # Should be JSON serializable
            json_str = json.dumps(tool)
            parsed = json.loads(json_str)
            assert parsed == tool
