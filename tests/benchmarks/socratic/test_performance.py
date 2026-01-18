"""Performance benchmarks for the Socratic Agent Generation System.

These benchmarks measure key performance metrics for workflow generation.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
from pathlib import Path


class TestSessionPerformance:
    """Benchmarks for session operations."""

    def test_session_creation_speed(self, benchmark, tmp_path):
        """Benchmark session creation speed."""
        from empathy_os.socratic import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "bench.json")

        def create_session():
            return builder.start_session("Benchmark test goal")

        result = benchmark(create_session)
        assert result is not None

    def test_session_save_speed(self, benchmark, tmp_path):
        """Benchmark session save speed."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.session import SocraticSession

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "bench.json")
        session = SocraticSession(session_id="bench-session")
        session.goal = "Benchmark test"
        session.collected_answers = {f"key_{i}": f"value_{i}" for i in range(100)}

        def save_session():
            builder.storage.save_session(session)

        benchmark(save_session)


class TestFormPerformance:
    """Benchmarks for form operations."""

    def test_form_creation_speed(self, benchmark):
        """Benchmark form creation speed."""
        from empathy_os.socratic.forms import Form, FormField, FieldType

        def create_form():
            fields = [
                FormField(
                    field_id=f"field_{i}",
                    label=f"Question {i}",
                    field_type=FieldType.TEXT,
                )
                for i in range(10)
            ]
            return Form(form_id="bench-form", title="Benchmark", fields=fields)

        result = benchmark(create_form)
        assert len(result.fields) == 10

    def test_form_validation_speed(self, benchmark):
        """Benchmark form validation speed."""
        from empathy_os.socratic.forms import Form, FormField, FieldType

        form = Form(
            form_id="bench-form",
            title="Benchmark",
            fields=[
                FormField(
                    field_id=f"field_{i}",
                    label=f"Question {i}",
                    field_type=FieldType.TEXT,
                    required=True,
                )
                for i in range(20)
            ],
        )

        answers = {f"field_{i}": f"answer_{i}" for i in range(20)}

        def validate():
            return form.validate(answers)

        result = benchmark(validate)
        assert result.is_valid


class TestBlueprintPerformance:
    """Benchmarks for blueprint operations."""

    def test_blueprint_creation_speed(self, benchmark):
        """Benchmark blueprint creation speed."""
        from empathy_os.socratic.blueprint import (
            WorkflowBlueprint,
            AgentSpec,
            ToolSpec,
        )

        def create_blueprint():
            agents = [
                AgentSpec(
                    agent_id=f"agent_{i}",
                    name=f"Agent {i}",
                    role="test",
                    tools=[
                        ToolSpec(tool_id=f"tool_{j}", name=f"Tool {j}")
                        for j in range(5)
                    ],
                )
                for i in range(10)
            ]
            return WorkflowBlueprint(
                workflow_id="bench-workflow",
                session_id="bench-session",
                name="Benchmark Workflow",
                agents=agents,
            )

        result = benchmark(create_blueprint)
        assert len(result.agents) == 10

    def test_blueprint_serialization_speed(self, benchmark):
        """Benchmark blueprint serialization speed."""
        from empathy_os.socratic.blueprint import (
            WorkflowBlueprint,
            AgentSpec,
            ToolSpec,
        )

        agents = [
            AgentSpec(
                agent_id=f"agent_{i}",
                name=f"Agent {i}",
                role="test",
                tools=[
                    ToolSpec(tool_id=f"tool_{j}", name=f"Tool {j}") for j in range(5)
                ],
            )
            for i in range(20)
        ]
        blueprint = WorkflowBlueprint(
            workflow_id="bench-workflow",
            session_id="bench-session",
            name="Benchmark Workflow",
            agents=agents,
        )

        def serialize():
            return blueprint.to_dict()

        result = benchmark(serialize)
        assert "workflow_id" in result


class TestEmbeddingsPerformance:
    """Benchmarks for embeddings operations."""

    def test_tfidf_embedding_speed(self, benchmark):
        """Benchmark TF-IDF embedding speed."""
        from empathy_os.socratic.embeddings import TFIDFEmbeddingProvider

        provider = TFIDFEmbeddingProvider(dimension=128)
        text = "I want to automate code reviews for Python projects with security focus"

        def embed():
            return provider.embed(text)

        result = benchmark(embed)
        assert len(result) == 128

    def test_tfidf_batch_embedding_speed(self, benchmark):
        """Benchmark TF-IDF batch embedding speed."""
        from empathy_os.socratic.embeddings import TFIDFEmbeddingProvider

        provider = TFIDFEmbeddingProvider(dimension=128)
        texts = [
            f"Goal number {i}: automate testing and code review" for i in range(100)
        ]

        def embed_batch():
            return provider.embed_batch(texts)

        result = benchmark(embed_batch)
        assert len(result) == 100

    def test_vector_search_speed(self, benchmark, tmp_path):
        """Benchmark vector search speed."""
        from empathy_os.socratic.embeddings import VectorStore

        store = VectorStore(storage_path=tmp_path / "vectors.json")

        # Add test data
        for i in range(100):
            store.add(
                goal_text=f"Goal {i}: automate {['testing', 'review', 'security', 'docs'][i % 4]}",
                domains=["code_quality"],
            )

        def search():
            return store.search("automate testing", top_k=10)

        result = benchmark(search)
        assert len(result) <= 10


class TestStoragePerformance:
    """Benchmarks for storage operations."""

    def test_json_save_speed(self, benchmark, tmp_path):
        """Benchmark JSON storage save speed."""
        from empathy_os.socratic.storage import JSONFileStorage
        from empathy_os.socratic.session import SocraticSession

        storage = JSONFileStorage(storage_path=tmp_path / "bench.json")
        session = SocraticSession(session_id="bench-session")
        session.goal = "Benchmark test"
        session.collected_answers = {f"key_{i}": f"value_{i}" for i in range(50)}

        def save():
            storage.save_session(session)

        benchmark(save)

    def test_json_load_speed(self, benchmark, tmp_path):
        """Benchmark JSON storage load speed."""
        from empathy_os.socratic.storage import JSONFileStorage
        from empathy_os.socratic.session import SocraticSession

        storage = JSONFileStorage(storage_path=tmp_path / "bench.json")

        # Pre-populate with sessions
        for i in range(100):
            session = SocraticSession(session_id=f"session-{i}")
            session.goal = f"Goal {i}"
            storage.save_session(session)

        def load():
            return storage.load_session("session-50")

        result = benchmark(load)
        assert result is not None

    def test_sqlite_save_speed(self, benchmark, tmp_path):
        """Benchmark SQLite storage save speed."""
        from empathy_os.socratic.storage import SQLiteStorage
        from empathy_os.socratic.session import SocraticSession

        storage = SQLiteStorage(db_path=tmp_path / "bench.db")
        session = SocraticSession(session_id="bench-session")
        session.goal = "Benchmark test"
        session.collected_answers = {f"key_{i}": f"value_{i}" for i in range(50)}

        def save():
            session.session_id = f"session-{id(session)}"  # Unique ID
            storage.save_session(session)

        benchmark(save)


class TestWorkflowGenerationPerformance:
    """Benchmarks for workflow generation."""

    def test_simple_workflow_generation_speed(self, benchmark, tmp_path):
        """Benchmark simple workflow generation speed."""
        from empathy_os.socratic import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "bench.json")
        session = builder.start_session("Automate code reviews")
        builder.submit_answers(session, {"languages": ["python"]})

        def generate():
            return builder.generate_workflow(session)

        result = benchmark(generate)
        assert result is not None


class TestDomainTemplatesPerformance:
    """Benchmarks for domain templates."""

    def test_domain_detection_speed(self, benchmark):
        """Benchmark domain detection speed."""
        from empathy_os.socratic.domain_templates import get_registry

        registry = get_registry()
        goals = [
            "Review code for security vulnerabilities",
            "Generate unit tests for my API",
            "Analyze code quality metrics",
            "Set up CI/CD pipeline",
            "Handle production incident",
        ]

        def detect():
            return [registry.detect_domain(goal) for goal in goals]

        result = benchmark(detect)
        assert len(result) == 5

    def test_template_lookup_speed(self, benchmark):
        """Benchmark template lookup speed."""
        from empathy_os.socratic.domain_templates import get_registry

        registry = get_registry()
        template_ids = [
            "code_reviewer",
            "security_scanner",
            "test_generator",
        ]

        def lookup():
            return [registry.get_agent_template(tid) for tid in template_ids]

        result = benchmark(lookup)
        assert len(result) == 3


class TestVisualEditorPerformance:
    """Benchmarks for visual editor."""

    def test_blueprint_to_editor_state_speed(self, benchmark, tmp_path):
        """Benchmark blueprint to editor state conversion speed."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "bench.json")
        session = builder.start_session("Test")
        builder.submit_answers(session, {})
        blueprint = builder.generate_workflow(session)

        visualizer = WorkflowVisualizer()

        def convert():
            return visualizer.from_blueprint(blueprint)

        result = benchmark(convert)
        assert result is not None

    def test_react_flow_schema_generation_speed(self, benchmark, tmp_path):
        """Benchmark React Flow schema generation speed."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.visual_editor import generate_react_flow_schema

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "bench.json")
        session = builder.start_session("Test")
        builder.submit_answers(session, {})
        blueprint = builder.generate_workflow(session)

        def generate():
            return generate_react_flow_schema(blueprint)

        result = benchmark(generate)
        assert "nodes" in result


class TestMCPServerPerformance:
    """Benchmarks for MCP server."""

    def test_tool_call_speed(self, benchmark, tmp_path):
        """Benchmark MCP tool call speed."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=tmp_path)

        def call_tool():
            return server.call_tool("socratic_start_session", {})

        result = benchmark(call_tool)
        assert "session_id" in result

    def test_list_tools_speed(self, benchmark, tmp_path):
        """Benchmark MCP list tools speed."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=tmp_path)

        def list_tools():
            return server.list_tools()

        result = benchmark(list_tools)
        assert len(result) > 0
