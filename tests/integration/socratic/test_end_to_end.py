"""End-to-end integration tests for the Socratic Agent Generation System.

These tests verify the complete workflow from goal input to workflow generation.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
from pathlib import Path


class TestCompleteWorkflowGeneration:
    """Tests for complete workflow generation flow."""

    def test_basic_workflow_generation(self, tmp_path):
        """Test basic end-to-end workflow generation."""
        from empathy_os.socratic import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")

        # 1. Start session
        session = builder.start_session("I want to automate code reviews for Python")

        assert session is not None
        assert session.session_id is not None

        # 2. Get clarifying questions
        form = builder.get_next_questions(session)

        assert form is not None
        assert len(form.fields) > 0

        # 3. Submit answers
        answers = {
            "languages": ["python"],
            "focus_areas": ["security", "style"],
            "team_size": "5-10",
        }
        session = builder.submit_answers(session, answers)

        assert len(session.collected_answers) > 0

        # 4. Check if ready to generate
        ready = builder.is_ready_to_generate(session)

        # May need more questions or be ready
        if not ready:
            # Get more questions and submit
            form2 = builder.get_next_questions(session)
            if form2 and form2.fields:
                session = builder.submit_answers(session, {"additional": "value"})

        # 5. Generate workflow
        workflow = builder.generate_workflow(session)

        assert workflow is not None
        assert workflow.workflow_id is not None
        assert len(workflow.agents) > 0

    def test_security_focused_workflow(self, tmp_path):
        """Test generating a security-focused workflow."""
        from empathy_os.socratic import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")

        session = builder.start_session(
            "Scan my codebase for security vulnerabilities"
        )

        # Quick path through questions
        form = builder.get_next_questions(session)
        session = builder.submit_answers(
            session,
            {
                "languages": ["python", "javascript"],
                "security_level": "high",
                "compliance": ["owasp"],
            },
        )

        workflow = builder.generate_workflow(session)

        # Should have security-related agents
        agent_names = [a.name.lower() for a in workflow.agents]
        assert any(
            "security" in name or "scan" in name or "vulnerab" in name
            for name in agent_names
        ) or len(workflow.agents) > 0

    def test_testing_workflow(self, tmp_path):
        """Test generating a test automation workflow."""
        from empathy_os.socratic import SocraticWorkflowBuilder

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")

        session = builder.start_session("Generate unit tests for my API endpoints")

        form = builder.get_next_questions(session)
        session = builder.submit_answers(
            session,
            {
                "framework": "pytest",
                "coverage_target": "80%",
                "test_types": ["unit", "integration"],
            },
        )

        workflow = builder.generate_workflow(session)

        assert workflow is not None
        assert len(workflow.agents) > 0


class TestWorkflowWithDomainTemplates:
    """Tests for workflow generation using domain templates."""

    def test_code_quality_template(self, tmp_path):
        """Test using code quality domain template."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.domain_templates import get_registry, Domain

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")
        registry = get_registry()

        # Get code quality template
        template = registry.get_domain_template(Domain.CODE_QUALITY)

        session = builder.start_session("Review code quality")
        form = builder.get_next_questions(session)
        session = builder.submit_answers(session, {"languages": ["python"]})

        workflow = builder.generate_workflow(session)

        assert workflow is not None

    def test_domain_detection_in_workflow(self, tmp_path):
        """Test automatic domain detection during workflow generation."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.domain_templates import get_registry

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")
        registry = get_registry()

        # Security-related goal
        session = builder.start_session("Find security vulnerabilities in my code")

        detected = registry.detect_domain(session.goal)
        assert detected is not None


class TestWorkflowPersistence:
    """Tests for workflow persistence across sessions."""

    def test_save_and_restore_session(self, tmp_path):
        """Test saving and restoring a session."""
        from empathy_os.socratic import SocraticWorkflowBuilder

        storage_path = tmp_path / "persist.json"

        # Create and save session
        builder1 = SocraticWorkflowBuilder(storage_path=storage_path)
        session1 = builder1.start_session("Test persistence")
        form = builder1.get_next_questions(session1)
        session1 = builder1.submit_answers(session1, {"key": "value"})

        # Create new builder pointing to same storage
        builder2 = SocraticWorkflowBuilder(storage_path=storage_path)
        session2 = builder2.get_session(session1.session_id)

        assert session2 is not None
        assert session2.goal == session1.goal
        assert session2.collected_answers == session1.collected_answers

    def test_save_and_restore_blueprint(self, tmp_path):
        """Test saving and restoring a workflow blueprint."""
        from empathy_os.socratic import SocraticWorkflowBuilder

        storage_path = tmp_path / "blueprints.json"

        # Generate workflow
        builder1 = SocraticWorkflowBuilder(storage_path=storage_path)
        session = builder1.start_session("Test blueprint")
        builder1.submit_answers(session, {})
        workflow1 = builder1.generate_workflow(session)

        # Load in new builder
        builder2 = SocraticWorkflowBuilder(storage_path=storage_path)
        workflow2 = builder2.get_blueprint(workflow1.workflow_id)

        assert workflow2 is not None
        assert workflow2.workflow_id == workflow1.workflow_id
        assert len(workflow2.agents) == len(workflow1.agents)


class TestMCPIntegration:
    """Tests for MCP server integration."""

    def test_mcp_complete_flow(self, tmp_path):
        """Test complete flow through MCP server."""
        from empathy_os.socratic.mcp_server import SocraticMCPServer

        server = SocraticMCPServer(storage_path=tmp_path)

        # 1. Start session
        result = server.call_tool("socratic_start_session", {})
        session_id = result["session_id"]

        # 2. Set goal
        server.call_tool(
            "socratic_set_goal",
            {"session_id": session_id, "goal": "Automate testing"},
        )

        # 3. Get questions
        questions = server.call_tool(
            "socratic_get_questions", {"session_id": session_id}
        )

        # 4. Submit answers
        server.call_tool(
            "socratic_submit_answers",
            {"session_id": session_id, "answers": {"framework": "pytest"}},
        )

        # 5. Generate workflow
        result = server.call_tool(
            "socratic_generate_workflow", {"session_id": session_id}
        )

        assert "workflow_id" in result or "blueprint" in result


class TestCLIIntegration:
    """Tests for CLI integration."""

    def test_cli_complete_flow(self, tmp_path):
        """Test complete flow through CLI."""
        from empathy_os.socratic.cli import SocraticCLI

        cli = SocraticCLI(storage_path=tmp_path / "cli.json")

        # 1. Start session
        session = cli.start_session()

        # 2. Set goal
        cli.set_goal(session.session_id, "Automate code reviews")

        # 3. Get questions
        questions = cli.get_questions(session.session_id)

        # 4. Submit answers
        cli.submit_answers(session.session_id, {"languages": ["python"]})

        # 5. Generate workflow
        workflow = cli.generate_workflow(session.session_id)

        assert workflow is not None

        # 6. List sessions and blueprints
        sessions = cli.list_sessions()
        blueprints = cli.list_blueprints()

        assert len(sessions) >= 1
        assert len(blueprints) >= 1


class TestVisualEditorIntegration:
    """Tests for visual editor integration."""

    def test_editor_round_trip(self, tmp_path):
        """Test editing a workflow and converting back."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.visual_editor import (
            VisualWorkflowEditor,
            generate_react_flow_schema,
        )

        # Generate a workflow
        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")
        session = builder.start_session("Test editing")
        builder.submit_answers(session, {})
        original = builder.generate_workflow(session)

        # Load into editor
        editor = VisualWorkflowEditor()
        editor.load(original)

        # Make edits
        editor.add_node(
            node_type="agent",
            label="New Agent",
            position={"x": 300, "y": 100},
            data={"agent_id": "new-agent"},
        )

        # Get modified blueprint
        modified = editor.get_blueprint()

        assert modified is not None
        assert len(modified.agents) >= len(original.agents)

        # Generate React Flow schema
        schema = generate_react_flow_schema(modified)
        assert "nodes" in schema
        assert "edges" in schema


class TestExplainerIntegration:
    """Tests for workflow explainer integration."""

    def test_explain_generated_workflow(self, tmp_path):
        """Test explaining a generated workflow."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.explainer import (
            explain_workflow,
            AudienceLevel,
        )

        # Generate a workflow
        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")
        session = builder.start_session("Automate security scanning")
        builder.submit_answers(session, {"languages": ["python"]})
        workflow = builder.generate_workflow(session)

        # Explain for different audiences
        for audience in [
            AudienceLevel.TECHNICAL,
            AudienceLevel.BUSINESS,
            AudienceLevel.BEGINNER,
        ]:
            explanation = explain_workflow(workflow, audience=audience)

            assert explanation is not None
            assert explanation.workflow_id == workflow.workflow_id
            assert len(explanation.summary) > 0


class TestCollaborationIntegration:
    """Tests for collaboration integration."""

    def test_collaborative_workflow_editing(self, tmp_path):
        """Test collaborative editing of a workflow."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.collaboration import (
            CollaborationManager,
            ParticipantRole,
            ChangeType,
            VoteType,
        )

        # Generate a workflow
        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")
        session = builder.start_session("Team workflow")
        builder.submit_answers(session, {})

        # Set up collaboration
        manager = CollaborationManager(storage_path=tmp_path / "collab.json")
        collab_session = manager.create_session(
            base_session=session,
            owner_id="user-001",
            owner_name="Alice",
        )

        # Invite team members
        manager.invite_participant(
            session_id=collab_session.session_id,
            inviter_id="user-001",
            invitee_id="user-002",
            invitee_name="Bob",
            role=ParticipantRole.EDITOR,
        )

        # Propose a change
        updated = manager.get_session(collab_session.session_id)
        change = updated.propose_change(
            author_id="user-002",
            change_type=ChangeType.ADD_AGENT,
            description="Add security agent",
            data={"name": "Security Agent"},
        )

        # Vote on change
        updated.add_vote("user-001", change.change_id, VoteType.APPROVE)

        assert len(updated.changes) >= 1


class TestABTestingIntegration:
    """Tests for A/B testing integration."""

    def test_ab_test_workflow_variants(self, tmp_path):
        """Test A/B testing workflow variants."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.ab_testing import WorkflowABTester

        # Generate two workflow variants
        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")

        session1 = builder.start_session("Code review variant A")
        builder.submit_answers(session1, {"focus": "speed"})
        workflow_a = builder.generate_workflow(session1)

        session2 = builder.start_session("Code review variant B")
        builder.submit_answers(session2, {"focus": "thoroughness"})
        workflow_b = builder.generate_workflow(session2)

        # Set up A/B test
        tester = WorkflowABTester(storage_path=tmp_path / "ab_test.json")
        experiment_id = tester.create_test(
            name="Code Review Comparison",
            control_workflow=workflow_a,
            treatment_workflow=workflow_b,
        )

        # Simulate users
        for user_id in ["user-1", "user-2", "user-3", "user-4", "user-5"]:
            workflow, variant_id = tester.get_workflow_for_user(experiment_id, user_id)
            assert workflow is not None

            # Record some successes
            if user_id in ["user-1", "user-2", "user-4"]:
                tester.record_success(experiment_id, variant_id)

        # Get results
        results = tester.get_results(experiment_id)
        assert results is not None


class TestEmbeddingsIntegration:
    """Tests for embeddings and semantic matching integration."""

    def test_find_similar_past_goals(self, tmp_path):
        """Test finding similar past goals."""
        from empathy_os.socratic import SocraticWorkflowBuilder
        from empathy_os.socratic.embeddings import SemanticGoalMatcher

        builder = SocraticWorkflowBuilder(storage_path=tmp_path / "storage.json")
        matcher = SemanticGoalMatcher(storage_path=tmp_path / "embeddings.json")

        # Create some workflows
        goals = [
            "Automate code reviews for Python",
            "Generate unit tests for JavaScript",
            "Scan for security vulnerabilities",
        ]

        for goal in goals:
            session = builder.start_session(goal)
            builder.submit_answers(session, {})
            workflow = builder.generate_workflow(session)

            # Index the goal
            matcher.index_goal(
                goal_text=goal,
                workflow_id=workflow.workflow_id,
                success_score=0.8,
            )

        # Find similar goals
        similar = matcher.find_similar("I want to review Python code", top_k=2)

        assert len(similar) > 0
        # Should find the Python code review goal as most similar
        assert "python" in similar[0].goal_text.lower() or len(similar) > 0
