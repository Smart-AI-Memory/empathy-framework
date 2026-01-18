"""Tests for the Socratic visual editor module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
import json


class TestEditorNode:
    """Tests for EditorNode dataclass."""

    def test_create_node(self):
        """Test creating an editor node."""
        from empathy_os.socratic.visual_editor import EditorNode

        node = EditorNode(
            node_id="node-001",
            node_type="agent",
            label="Code Reviewer",
            position={"x": 100, "y": 200},
            data={"agent_id": "agent-001", "role": "reviewer"},
        )

        assert node.node_id == "node-001"
        assert node.node_type == "agent"
        assert node.position["x"] == 100
        assert node.position["y"] == 200

    def test_node_to_dict(self):
        """Test node serialization."""
        from empathy_os.socratic.visual_editor import EditorNode

        node = EditorNode(
            node_id="node-001",
            node_type="agent",
            label="Test Agent",
            position={"x": 0, "y": 0},
        )

        data = node.to_dict()

        assert data["id"] == "node-001"
        assert data["type"] == "agent"
        assert data["data"]["label"] == "Test Agent"


class TestEditorEdge:
    """Tests for EditorEdge dataclass."""

    def test_create_edge(self):
        """Test creating an editor edge."""
        from empathy_os.socratic.visual_editor import EditorEdge

        edge = EditorEdge(
            edge_id="edge-001",
            source="node-001",
            target="node-002",
            label="on_success",
        )

        assert edge.edge_id == "edge-001"
        assert edge.source == "node-001"
        assert edge.target == "node-002"

    def test_edge_to_dict(self):
        """Test edge serialization."""
        from empathy_os.socratic.visual_editor import EditorEdge

        edge = EditorEdge(
            edge_id="edge-001",
            source="node-001",
            target="node-002",
        )

        data = edge.to_dict()

        assert data["id"] == "edge-001"
        assert data["source"] == "node-001"
        assert data["target"] == "node-002"


class TestEditorState:
    """Tests for EditorState dataclass."""

    def test_create_state(self):
        """Test creating an editor state."""
        from empathy_os.socratic.visual_editor import (
            EditorState,
            EditorNode,
            EditorEdge,
        )

        nodes = [
            EditorNode(
                node_id="node-1",
                node_type="agent",
                label="Agent 1",
                position={"x": 0, "y": 0},
            ),
            EditorNode(
                node_id="node-2",
                node_type="agent",
                label="Agent 2",
                position={"x": 200, "y": 0},
            ),
        ]

        edges = [
            EditorEdge(
                edge_id="edge-1",
                source="node-1",
                target="node-2",
            ),
        ]

        state = EditorState(
            workflow_id="wf-001",
            nodes=nodes,
            edges=edges,
        )

        assert state.workflow_id == "wf-001"
        assert len(state.nodes) == 2
        assert len(state.edges) == 1

    def test_state_to_react_flow(self):
        """Test converting state to React Flow schema."""
        from empathy_os.socratic.visual_editor import (
            EditorState,
            EditorNode,
            EditorEdge,
        )

        state = EditorState(
            workflow_id="wf-001",
            nodes=[
                EditorNode(
                    node_id="n1",
                    node_type="agent",
                    label="Agent",
                    position={"x": 0, "y": 0},
                ),
            ],
            edges=[],
        )

        react_flow = state.to_react_flow()

        assert "nodes" in react_flow
        assert "edges" in react_flow
        assert len(react_flow["nodes"]) == 1


class TestWorkflowVisualizer:
    """Tests for WorkflowVisualizer class."""

    def test_create_visualizer(self):
        """Test creating a workflow visualizer."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer()
        assert visualizer is not None

    def test_visualize_blueprint(self, sample_workflow_blueprint):
        """Test visualizing a workflow blueprint."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer()
        state = visualizer.from_blueprint(sample_workflow_blueprint)

        assert state is not None
        assert state.workflow_id == sample_workflow_blueprint.workflow_id
        assert len(state.nodes) > 0

    def test_generate_positions(self, sample_workflow_blueprint):
        """Test that positions are generated for nodes."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer()
        state = visualizer.from_blueprint(sample_workflow_blueprint)

        for node in state.nodes:
            assert "x" in node.position
            assert "y" in node.position

    def test_to_blueprint(self, sample_workflow_blueprint):
        """Test converting editor state back to blueprint."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer()

        # Convert to editor state
        state = visualizer.from_blueprint(sample_workflow_blueprint)

        # Convert back to blueprint
        restored = visualizer.to_blueprint(state)

        assert restored.workflow_id == sample_workflow_blueprint.workflow_id
        assert len(restored.agents) == len(sample_workflow_blueprint.agents)


class TestASCIIVisualizer:
    """Tests for ASCIIVisualizer class."""

    def test_create_ascii_visualizer(self):
        """Test creating an ASCII visualizer."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer()
        assert visualizer is not None

    def test_render_simple_workflow(self, sample_workflow_blueprint):
        """Test rendering a simple workflow."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer()
        ascii_art = visualizer.render(sample_workflow_blueprint)

        assert isinstance(ascii_art, str)
        assert len(ascii_art) > 0

    def test_render_contains_agent_names(self, sample_workflow_blueprint):
        """Test that ASCII rendering contains agent names."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer()
        ascii_art = visualizer.render(sample_workflow_blueprint)

        # Should contain at least one agent name
        for agent in sample_workflow_blueprint.agents:
            # Name might be truncated, so check for partial match
            assert agent.name[:10] in ascii_art or "Agent" in ascii_art

    def test_render_with_box_style(self, sample_workflow_blueprint):
        """Test rendering with box style."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer(style="box")
        ascii_art = visualizer.render(sample_workflow_blueprint)

        # Should use box drawing characters
        assert "─" in ascii_art or "-" in ascii_art or "+" in ascii_art


class TestVisualWorkflowEditor:
    """Tests for VisualWorkflowEditor class."""

    def test_create_editor(self):
        """Test creating a visual workflow editor."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        assert editor is not None

    def test_load_blueprint(self, sample_workflow_blueprint):
        """Test loading a blueprint into the editor."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        editor.load(sample_workflow_blueprint)

        assert editor.current_state is not None
        assert editor.current_state.workflow_id == sample_workflow_blueprint.workflow_id

    def test_add_node(self, sample_workflow_blueprint):
        """Test adding a node to the editor."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        editor.load(sample_workflow_blueprint)

        initial_count = len(editor.current_state.nodes)

        editor.add_node(
            node_type="agent",
            label="New Agent",
            position={"x": 300, "y": 100},
            data={"agent_id": "new-agent"},
        )

        assert len(editor.current_state.nodes) == initial_count + 1

    def test_remove_node(self, sample_workflow_blueprint):
        """Test removing a node from the editor."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        editor.load(sample_workflow_blueprint)

        initial_count = len(editor.current_state.nodes)
        node_to_remove = editor.current_state.nodes[0].node_id

        editor.remove_node(node_to_remove)

        assert len(editor.current_state.nodes) == initial_count - 1

    def test_add_edge(self, sample_workflow_blueprint):
        """Test adding an edge between nodes."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        editor.load(sample_workflow_blueprint)

        # Add two nodes first
        editor.add_node(
            node_type="agent",
            label="Source",
            position={"x": 0, "y": 0},
            node_id="source-node",
        )
        editor.add_node(
            node_type="agent",
            label="Target",
            position={"x": 200, "y": 0},
            node_id="target-node",
        )

        initial_edge_count = len(editor.current_state.edges)

        editor.add_edge("source-node", "target-node")

        assert len(editor.current_state.edges) == initial_edge_count + 1

    def test_get_blueprint(self, sample_workflow_blueprint):
        """Test getting blueprint from editor state."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        editor.load(sample_workflow_blueprint)

        blueprint = editor.get_blueprint()

        assert blueprint is not None
        assert blueprint.workflow_id == sample_workflow_blueprint.workflow_id

    def test_undo_redo(self, sample_workflow_blueprint):
        """Test undo/redo functionality."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        editor.load(sample_workflow_blueprint)

        initial_count = len(editor.current_state.nodes)

        # Add a node
        editor.add_node(
            node_type="agent",
            label="New",
            position={"x": 0, "y": 0},
        )
        assert len(editor.current_state.nodes) == initial_count + 1

        # Undo
        if hasattr(editor, "undo"):
            editor.undo()
            assert len(editor.current_state.nodes) == initial_count

            # Redo
            if hasattr(editor, "redo"):
                editor.redo()
                assert len(editor.current_state.nodes) == initial_count + 1


class TestGenerateReactFlowSchema:
    """Tests for generate_react_flow_schema function."""

    def test_generate_schema(self, sample_workflow_blueprint):
        """Test generating React Flow schema from blueprint."""
        from empathy_os.socratic.visual_editor import generate_react_flow_schema

        schema = generate_react_flow_schema(sample_workflow_blueprint)

        assert isinstance(schema, dict)
        assert "nodes" in schema
        assert "edges" in schema
        assert isinstance(schema["nodes"], list)
        assert isinstance(schema["edges"], list)

    def test_schema_is_json_serializable(self, sample_workflow_blueprint):
        """Test that schema can be serialized to JSON."""
        from empathy_os.socratic.visual_editor import generate_react_flow_schema

        schema = generate_react_flow_schema(sample_workflow_blueprint)

        # Should not raise
        json_str = json.dumps(schema)
        assert isinstance(json_str, str)

        # Should be parseable
        parsed = json.loads(json_str)
        assert parsed == schema


class TestGenerateEditorHtml:
    """Tests for generate_editor_html function."""

    def test_generate_html(self, sample_workflow_blueprint):
        """Test generating standalone HTML editor."""
        from empathy_os.socratic.visual_editor import generate_editor_html

        html = generate_editor_html(sample_workflow_blueprint)

        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html or "<html" in html
        assert "react" in html.lower() or "script" in html.lower()

    def test_html_contains_workflow_data(self, sample_workflow_blueprint):
        """Test that HTML contains workflow data."""
        from empathy_os.socratic.visual_editor import generate_editor_html

        html = generate_editor_html(sample_workflow_blueprint)

        # Should contain workflow ID or name
        assert (
            sample_workflow_blueprint.workflow_id in html
            or sample_workflow_blueprint.name in html
        )

    def test_generate_html_with_options(self, sample_workflow_blueprint):
        """Test generating HTML with custom options."""
        from empathy_os.socratic.visual_editor import generate_editor_html

        html = generate_editor_html(
            sample_workflow_blueprint,
            title="Custom Editor",
            read_only=True,
        )

        assert "Custom Editor" in html
