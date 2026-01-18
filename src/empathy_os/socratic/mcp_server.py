"""MCP Server for Socratic Agent Generation System.

Exposes the Socratic workflow builder as MCP tools for Claude Desktop/Code.

Usage:
    python -m empathy_os.socratic.mcp_server

Or add to Claude Desktop config:
    {
        "mcpServers": {
            "socratic": {
                "command": "python",
                "args": ["-m", "empathy_os.socratic.mcp_server"],
                "env": {
                    "ANTHROPIC_API_KEY": "your-key"
                }
            }
        }
    }

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict
from typing import Any

logger = logging.getLogger(__name__)

# MCP Protocol Types
MCP_VERSION = "2024-11-05"

# Tool definitions for the Socratic system
SOCRATIC_TOOLS = [
    {
        "name": "socratic_start_session",
        "description": "Start a new Socratic workflow builder session. Returns a session ID and initial state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Optional initial goal. If not provided, session starts in AWAITING_GOAL state."
                }
            },
            "required": []
        }
    },
    {
        "name": "socratic_set_goal",
        "description": "Set or update the goal for a session. Triggers goal analysis and domain detection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to update"
                },
                "goal": {
                    "type": "string",
                    "description": "The user's goal in free-form text"
                }
            },
            "required": ["session_id", "goal"]
        }
    },
    {
        "name": "socratic_get_questions",
        "description": "Get the next set of clarifying questions for a session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID"
                }
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "socratic_submit_answers",
        "description": "Submit answers to clarifying questions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID"
                },
                "answers": {
                    "type": "object",
                    "description": "Dictionary of field_id -> answer value"
                }
            },
            "required": ["session_id", "answers"]
        }
    },
    {
        "name": "socratic_generate_workflow",
        "description": "Generate the workflow once all questions are answered. Returns agent blueprints and success criteria.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID"
                }
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "socratic_list_sessions",
        "description": "List all saved Socratic sessions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["all", "active", "completed"],
                    "description": "Filter sessions by status"
                }
            },
            "required": []
        }
    },
    {
        "name": "socratic_get_session",
        "description": "Get details of a specific session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to retrieve"
                }
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "socratic_list_blueprints",
        "description": "List all saved workflow blueprints.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain_filter": {
                    "type": "string",
                    "description": "Optional domain to filter by (e.g., 'code_review', 'security')"
                }
            },
            "required": []
        }
    },
    {
        "name": "socratic_analyze_goal",
        "description": "Analyze a goal using LLM to detect domains, requirements, and ambiguities without starting a full session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The goal to analyze"
                }
            },
            "required": ["goal"]
        }
    },
    {
        "name": "socratic_recommend_agents",
        "description": "Get agent recommendations based on requirements and historical success data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of domains (e.g., ['code_review', 'security'])"
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Programming languages involved"
                },
                "quality_focus": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Quality focus areas (e.g., ['security', 'performance'])"
                }
            },
            "required": ["domains"]
        }
    }
]


class SocraticMCPServer:
    """MCP Server exposing Socratic workflow builder tools."""

    def __init__(self):
        """Initialize the MCP server."""
        self._sessions: dict[str, Any] = {}
        self._builder = None
        self._storage = None
        self._llm_analyzer = None
        self._feedback_loop = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Lazily initialize components."""
        if self._initialized:
            return

        try:
            from .engine import SocraticWorkflowBuilder
            from .storage import JSONFileStorage, StorageManager
            from .llm_analyzer import LLMGoalAnalyzer
            from .feedback import FeedbackLoop

            # Initialize storage
            self._storage = JSONFileStorage()
            StorageManager.initialize(self._storage)

            # Initialize builder
            self._builder = SocraticWorkflowBuilder()

            # Initialize LLM analyzer if API key available
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self._llm_analyzer = LLMGoalAnalyzer(api_key=api_key)

            # Initialize feedback loop
            self._feedback_loop = FeedbackLoop(self._storage)

            self._initialized = True
            logger.info("Socratic MCP Server initialized successfully")

        except ImportError as e:
            logger.warning(f"Some components not available: {e}")
            self._initialized = True

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Handle a tool call from Claude.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result as dictionary
        """
        await self._ensure_initialized()

        handlers = {
            "socratic_start_session": self._handle_start_session,
            "socratic_set_goal": self._handle_set_goal,
            "socratic_get_questions": self._handle_get_questions,
            "socratic_submit_answers": self._handle_submit_answers,
            "socratic_generate_workflow": self._handle_generate_workflow,
            "socratic_list_sessions": self._handle_list_sessions,
            "socratic_get_session": self._handle_get_session,
            "socratic_list_blueprints": self._handle_list_blueprints,
            "socratic_analyze_goal": self._handle_analyze_goal,
            "socratic_recommend_agents": self._handle_recommend_agents,
        }

        handler = handlers.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}

        try:
            return await handler(arguments)
        except Exception as e:
            logger.exception(f"Error handling {name}")
            return {"error": str(e)}

    async def _handle_start_session(self, args: dict[str, Any]) -> dict[str, Any]:
        """Start a new Socratic session."""
        goal = args.get("goal")

        session = self._builder.start_session(goal)
        self._sessions[session.session_id] = session

        # Persist session
        if self._storage:
            self._storage.save_session(session)

        result = {
            "session_id": session.session_id,
            "state": session.state.value,
            "message": "Session started successfully"
        }

        if goal:
            result["goal"] = goal
            result["detected_domains"] = list(session.detected_domains) if session.detected_domains else []

        return result

    async def _handle_set_goal(self, args: dict[str, Any]) -> dict[str, Any]:
        """Set goal for a session."""
        session_id = args["session_id"]
        goal = args["goal"]

        session = self._get_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}

        # Use LLM analyzer if available
        analysis = None
        if self._llm_analyzer:
            try:
                analysis = await self._llm_analyzer.analyze_goal(goal)
            except Exception as e:
                logger.warning(f"LLM analysis failed, using fallback: {e}")

        session = self._builder.set_goal(session, goal)
        self._sessions[session_id] = session

        if self._storage:
            self._storage.save_session(session)

        result = {
            "session_id": session_id,
            "state": session.state.value,
            "goal": goal,
            "detected_domains": list(session.detected_domains) if session.detected_domains else []
        }

        if analysis:
            result["llm_analysis"] = {
                "primary_domain": analysis.primary_domain,
                "confidence": analysis.confidence,
                "ambiguities": analysis.ambiguities,
                "suggested_questions": analysis.suggested_questions[:3]
            }

        return result

    async def _handle_get_questions(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get clarifying questions for a session."""
        session_id = args["session_id"]

        session = self._get_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}

        form = self._builder.get_next_questions(session)
        if not form:
            return {
                "session_id": session_id,
                "state": session.state.value,
                "questions": [],
                "message": "No more questions - ready to generate workflow"
            }

        # Convert form to JSON-serializable format
        questions = []
        for field in form.fields:
            q = {
                "field_id": field.field_id,
                "type": field.field_type.value,
                "label": field.label,
                "required": field.required
            }
            if field.options:
                q["options"] = field.options
            if field.placeholder:
                q["placeholder"] = field.placeholder
            if field.help_text:
                q["help_text"] = field.help_text
            if field.default_value is not None:
                q["default"] = field.default_value
            questions.append(q)

        return {
            "session_id": session_id,
            "state": session.state.value,
            "form_id": form.form_id,
            "form_title": form.title,
            "questions": questions
        }

    async def _handle_submit_answers(self, args: dict[str, Any]) -> dict[str, Any]:
        """Submit answers to questions."""
        session_id = args["session_id"]
        answers = args["answers"]

        session = self._get_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}

        session = self._builder.submit_answers(session, answers)
        self._sessions[session_id] = session

        if self._storage:
            self._storage.save_session(session)

        ready = self._builder.is_ready_to_generate(session)

        return {
            "session_id": session_id,
            "state": session.state.value,
            "ready_to_generate": ready,
            "message": "Ready to generate workflow" if ready else "More questions available"
        }

    async def _handle_generate_workflow(self, args: dict[str, Any]) -> dict[str, Any]:
        """Generate workflow from session."""
        session_id = args["session_id"]

        session = self._get_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}

        if not self._builder.is_ready_to_generate(session):
            return {
                "error": "Session not ready for generation",
                "state": session.state.value
            }

        workflow = self._builder.generate_workflow(session)

        # Save blueprint
        if self._storage:
            self._storage.save_blueprint(workflow.blueprint)
            self._storage.save_session(session)

        # Convert to JSON-serializable format
        agents = []
        for agent in workflow.blueprint.agents:
            agents.append({
                "agent_id": agent.agent_id,
                "name": agent.name,
                "role": agent.role.value,
                "description": agent.description,
                "tools": [t.tool_id for t in agent.tools]
            })

        stages = []
        for stage in workflow.blueprint.stages:
            stages.append({
                "stage_id": stage.stage_id,
                "name": stage.name,
                "agent_ids": stage.agent_ids,
                "dependencies": stage.dependencies
            })

        metrics = []
        for metric in workflow.success_criteria.metrics:
            metrics.append({
                "metric_id": metric.metric_id,
                "name": metric.name,
                "description": metric.description,
                "type": metric.metric_type.value,
                "target": metric.target_value
            })

        return {
            "session_id": session_id,
            "blueprint_id": workflow.blueprint.blueprint_id,
            "workflow_name": workflow.blueprint.name,
            "agents": agents,
            "stages": stages,
            "success_metrics": metrics,
            "state": session.state.value
        }

    async def _handle_list_sessions(self, args: dict[str, Any]) -> dict[str, Any]:
        """List all sessions."""
        status_filter = args.get("status_filter", "all")

        sessions = []

        # Get from storage
        if self._storage:
            stored = self._storage.list_sessions()
            for s in stored:
                if status_filter == "all":
                    sessions.append(s)
                elif status_filter == "active" and s.get("state") != "completed":
                    sessions.append(s)
                elif status_filter == "completed" and s.get("state") == "completed":
                    sessions.append(s)

        # Add in-memory sessions not yet persisted
        for sid, session in self._sessions.items():
            if not any(s.get("session_id") == sid for s in sessions):
                sessions.append({
                    "session_id": session.session_id,
                    "state": session.state.value,
                    "goal": session.goal,
                    "created_at": session.created_at.isoformat() if session.created_at else None
                })

        return {
            "sessions": sessions,
            "count": len(sessions)
        }

    async def _handle_get_session(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get session details."""
        session_id = args["session_id"]

        session = self._get_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}

        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "goal": session.goal,
            "detected_domains": list(session.detected_domains) if session.detected_domains else [],
            "answers": session.answers,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None
        }

    async def _handle_list_blueprints(self, args: dict[str, Any]) -> dict[str, Any]:
        """List all blueprints."""
        domain_filter = args.get("domain_filter")

        blueprints = []

        if self._storage:
            stored = self._storage.list_blueprints()
            for bp in stored:
                if domain_filter:
                    domains = bp.get("domains", [])
                    if domain_filter not in domains:
                        continue
                blueprints.append(bp)

        return {
            "blueprints": blueprints,
            "count": len(blueprints)
        }

    async def _handle_analyze_goal(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze a goal without starting a session."""
        goal = args["goal"]

        # Use LLM analyzer if available
        if self._llm_analyzer:
            try:
                analysis = await self._llm_analyzer.analyze_goal(goal)
                return {
                    "goal": goal,
                    "primary_domain": analysis.primary_domain,
                    "secondary_domains": analysis.secondary_domains,
                    "confidence": analysis.confidence,
                    "detected_requirements": analysis.detected_requirements,
                    "ambiguities": analysis.ambiguities,
                    "suggested_questions": analysis.suggested_questions,
                    "suggested_agents": analysis.suggested_agents,
                    "analysis_method": "llm"
                }
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}")

        # Fallback to keyword-based analysis
        domains = self._builder._detect_domains(goal)
        return {
            "goal": goal,
            "detected_domains": list(domains),
            "analysis_method": "keyword"
        }

    async def _handle_recommend_agents(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get agent recommendations."""
        domains = args["domains"]
        languages = args.get("languages", [])
        quality_focus = args.get("quality_focus", [])

        from .feedback import AdaptiveAgentGenerator
        from .generator import AgentGenerator

        # Use adaptive generator if feedback available
        if self._feedback_loop:
            adaptive_gen = AdaptiveAgentGenerator(self._feedback_loop.collector)
            context = {
                "domains": domains,
                "languages": languages,
                "quality_focus": quality_focus
            }
            recommendations = adaptive_gen.recommend_agents(context)
        else:
            # Use basic generator
            generator = AgentGenerator()
            recommendations = []
            for domain in domains:
                templates = generator._get_templates_for_domain(domain)
                for t in templates:
                    recommendations.append({
                        "template_id": t,
                        "domain": domain,
                        "confidence": 0.8
                    })

        return {
            "recommendations": recommendations,
            "count": len(recommendations)
        }

    def _get_session(self, session_id: str):
        """Get session from memory or storage."""
        # Check memory first
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Try loading from storage
        if self._storage:
            session = self._storage.load_session(session_id)
            if session:
                self._sessions[session_id] = session
                return session

        return None


async def run_mcp_server():
    """Run the MCP server using stdio transport."""
    server = SocraticMCPServer()

    # Read from stdin, write to stdout
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

    async def send_response(response: dict):
        """Send a JSON-RPC response."""
        data = json.dumps(response) + "\n"
        writer.write(data.encode())
        await writer.drain()

    async def handle_message(message: dict):
        """Handle an incoming JSON-RPC message."""
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        if method == "initialize":
            # MCP initialization
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": MCP_VERSION,
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "socratic-workflow-builder",
                        "version": "1.0.0"
                    }
                }
            }
            await send_response(response)

        elif method == "tools/list":
            # List available tools
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": SOCRATIC_TOOLS
                }
            }
            await send_response(response)

        elif method == "tools/call":
            # Execute a tool
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            result = await server.handle_tool_call(tool_name, tool_args)

            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
            await send_response(response)

        elif method == "notifications/initialized":
            # Client initialized notification - no response needed
            pass

        else:
            # Unknown method
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            await send_response(response)

    # Main message loop
    logger.info("Socratic MCP Server starting...")

    while True:
        try:
            line = await reader.readline()
            if not line:
                break

            message = json.loads(line.decode().strip())
            await handle_message(message)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
        except Exception as e:
            logger.exception(f"Error processing message: {e}")


def main():
    """Entry point for MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr  # Log to stderr, MCP uses stdout
    )

    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        logger.info("Server shutting down...")


if __name__ == "__main__":
    main()
