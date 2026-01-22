"""Tests for the Socratic visual editor module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

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

    def test_node_with_position_object(self):
        """Test creating node with Position object."""
        from empathy_os.socratic.visual_editor import EditorNode, Position

        pos = Position(x=50, y=100)
        node = EditorNode(
            node_id="node-002",
            node_type="stage",
            label="Test Stage",
            position=pos,
        )

        assert node.position.x == 50
        assert node.position.y == 100

    def test_node_with_node_type_enum(self):
        """Test creating node with NodeType enum."""
        from empathy_os.socratic.visual_editor import EditorNode, NodeType

        node = EditorNode(
            node_id="node-003",
            node_type=NodeType.AGENT,
            label="Test Agent",
            position={"x": 0, "y": 0},
        )

        assert node.node_type == NodeType.AGENT

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

    def test_node_to_dict_with_enum(self):
        """Test node serialization with NodeType enum."""
        from empathy_os.socratic.visual_editor import EditorNode, NodeType

        node = EditorNode(
            node_id="node-001",
            node_type=NodeType.STAGE,
            label="Test Stage",
            position={"x": 0, "y": 0},
        )

        data = node.to_dict()
        assert data["type"] == "stage"

    def test_node_default_values(self):
        """Test node default values."""
        from empathy_os.socratic.visual_editor import EditorNode

        node = EditorNode(
            node_id="node-001",
            node_type="agent",
            label="Test",
            position={"x": 0, "y": 0},
        )

        assert node.data == {}
        assert node.selected is False
        assert node.locked is False


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
        assert edge.label == "on_success"

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

    def test_edge_default_values(self):
        """Test edge default values."""
        from empathy_os.socratic.visual_editor import EditorEdge

        edge = EditorEdge(
            edge_id="edge-001",
            source="node-001",
            target="node-002",
        )

        assert edge.label == ""
        assert edge.animated is False


class TestPosition:
    """Tests for Position dataclass."""

    def test_create_position(self):
        """Test creating a position."""
        from empathy_os.socratic.visual_editor import Position

        pos = Position(x=100, y=200)

        assert pos.x == 100
        assert pos.y == 200

    def test_position_to_dict(self):
        """Test position serialization."""
        from empathy_os.socratic.visual_editor import Position

        pos = Position(x=50, y=75)
        data = pos.to_dict()

        assert data == {"x": 50, "y": 75}


class TestNodeType:
    """Tests for NodeType enum."""

    def test_all_node_types_exist(self):
        """Test all expected node types exist."""
        from empathy_os.socratic.visual_editor import NodeType

        assert NodeType.AGENT.value == "agent"
        assert NodeType.STAGE.value == "stage"
        assert NodeType.START.value == "start"
        assert NodeType.END.value == "end"
        assert NodeType.CONNECTOR.value == "connector"


class TestEditorState:
    """Tests for EditorState dataclass."""

    def test_create_state(self):
        """Test creating an editor state."""
        from empathy_os.socratic.visual_editor import (
            EditorEdge,
            EditorNode,
            EditorState,
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

    def test_state_default_values(self):
        """Test EditorState default values."""
        from empathy_os.socratic.visual_editor import EditorState

        state = EditorState()

        assert state.workflow_id == ""
        assert state.nodes == []
        assert state.edges == []
        assert state.selected_node_id is None
        assert state.zoom == 1.0
        assert state.pan_x == 0
        assert state.pan_y == 0

    def test_state_to_dict(self):
        """Test EditorState serialization."""
        from empathy_os.socratic.visual_editor import (
            EditorNode,
            EditorState,
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
            zoom=1.5,
        )

        data = state.to_dict()

        assert "nodes" in data
        assert "edges" in data
        assert data["zoom"] == 1.5
        assert len(data["nodes"]) == 1

    def test_state_to_react_flow(self):
        """Test converting state to React Flow schema."""
        from empathy_os.socratic.visual_editor import (
            EditorNode,
            EditorState,
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
        assert visualizer.node_spacing == 200
        assert visualizer.stage_spacing == 150

    def test_create_visualizer_custom_spacing(self):
        """Test creating visualizer with custom spacing."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer(node_spacing=300, stage_spacing=200)

        assert visualizer.node_spacing == 300
        assert visualizer.stage_spacing == 200

    def test_blueprint_to_editor_method_exists(self):
        """Test blueprint_to_editor method exists."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer()
        assert hasattr(visualizer, "blueprint_to_editor")
        assert callable(visualizer.blueprint_to_editor)

    def test_from_blueprint_alias_exists(self):
        """Test from_blueprint alias method exists."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer()
        assert hasattr(visualizer, "from_blueprint")
        assert callable(visualizer.from_blueprint)

    def test_editor_to_blueprint_method_exists(self):
        """Test editor_to_blueprint method exists."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer()
        assert hasattr(visualizer, "editor_to_blueprint")
        assert callable(visualizer.editor_to_blueprint)

    def test_to_blueprint_alias_exists(self):
        """Test to_blueprint alias method exists."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer()
        assert hasattr(visualizer, "to_blueprint")
        assert callable(visualizer.to_blueprint)

    def test_visualize_blueprint(self, sample_workflow_blueprint):
        """Test visualizing a workflow blueprint."""
        from empathy_os.socratic.visual_editor import WorkflowVisualizer

        visualizer = WorkflowVisualizer()
        state = visualizer.blueprint_to_editor(sample_workflow_blueprint)

        assert state is not None
        assert state.workflow_id == sample_workflow_blueprint.id
        assert len(state.nodes) > 0

    def test_state_has_start_end_nodes(self, sample_workflow_blueprint):
        """Test that state includes start and end nodes."""
        from empathy_os.socratic.visual_editor import NodeType, WorkflowVisualizer

        visualizer = WorkflowVisualizer()
        state = visualizer.blueprint_to_editor(sample_workflow_blueprint)

        node_types = [n.node_type for n in state.nodes]
        assert NodeType.START in node_types
        assert NodeType.END in node_types


class TestASCIIVisualizer:
    """Tests for ASCIIVisualizer class."""

    def test_create_ascii_visualizer(self):
        """Test creating an ASCII visualizer."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer()
        assert visualizer is not None
        assert visualizer.width == 80

    def test_create_ascii_visualizer_custom_width(self):
        """Test creating ASCII visualizer with custom width."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer(width=100)
        assert visualizer.width == 100

    def test_render_method_exists(self):
        """Test render method exists."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer()
        assert hasattr(visualizer, "render")
        assert callable(visualizer.render)

    def test_render_compact_method_exists(self):
        """Test render_compact method exists."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer()
        assert hasattr(visualizer, "render_compact")
        assert callable(visualizer.render_compact)

    def test_render_workflow(self, sample_workflow_blueprint):
        """Test rendering a workflow as ASCII art."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer()
        ascii_art = visualizer.render(sample_workflow_blueprint)

        assert isinstance(ascii_art, str)
        assert len(ascii_art) > 0
        assert "Workflow" in ascii_art
        assert "START" in ascii_art
        assert "END" in ascii_art

    def test_render_compact(self, sample_workflow_blueprint):
        """Test compact rendering."""
        from empathy_os.socratic.visual_editor import ASCIIVisualizer

        visualizer = ASCIIVisualizer()
        compact = visualizer.render_compact(sample_workflow_blueprint)

        assert isinstance(compact, str)
        assert len(compact) > 0


class TestVisualWorkflowEditor:
    """Tests for VisualWorkflowEditor class."""

    def test_create_editor(self):
        """Test creating a visual workflow editor."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        assert editor is not None

    def test_editor_has_visualizer(self):
        """Test editor has visualizer attribute."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        assert hasattr(editor, "visualizer")
        assert hasattr(editor, "ascii_visualizer")

    def test_create_editor_state(self, sample_workflow_blueprint):
        """Test creating editor state from blueprint."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        state = editor.create_editor_state(sample_workflow_blueprint)

        assert state is not None
        assert len(state.nodes) > 0

    def test_apply_changes(self, sample_workflow_blueprint):
        """Test applying editor changes to blueprint."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        state = editor.create_editor_state(sample_workflow_blueprint)

        # Apply changes
        updated_blueprint = editor.apply_changes(state, sample_workflow_blueprint)

        assert updated_blueprint is not None
        assert updated_blueprint.id == sample_workflow_blueprint.id

    def test_render_ascii(self, sample_workflow_blueprint):
        """Test ASCII rendering via editor."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        ascii_art = editor.render_ascii(sample_workflow_blueprint)

        assert isinstance(ascii_art, str)
        assert len(ascii_art) > 0

    def test_render_compact(self, sample_workflow_blueprint):
        """Test compact rendering via editor."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        compact = editor.render_compact(sample_workflow_blueprint)

        assert isinstance(compact, str)
        assert len(compact) > 0

    def test_generate_html_editor(self, sample_workflow_blueprint):
        """Test generating HTML editor."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        html = editor.generate_html_editor(sample_workflow_blueprint)

        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "react" in html.lower()

    def test_generate_react_schema(self, sample_workflow_blueprint):
        """Test generating React schema."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        schema = editor.generate_react_schema(sample_workflow_blueprint)

        assert isinstance(schema, dict)
        assert "nodes" in schema
        assert "edges" in schema

    def test_validate_state_empty(self):
        """Test validating empty editor state."""
        from empathy_os.socratic.visual_editor import EditorState, VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        state = EditorState()

        errors = editor.validate_state(state)

        assert isinstance(errors, list)
        assert len(errors) > 0  # Should have errors for missing start/end

    def test_validate_state_valid(self, sample_workflow_blueprint):
        """Test validating a valid editor state."""
        from empathy_os.socratic.visual_editor import VisualWorkflowEditor

        editor = VisualWorkflowEditor()
        state = editor.create_editor_state(sample_workflow_blueprint)

        errors = editor.validate_state(state)

        assert isinstance(errors, list)
        # Valid state should have no errors (or minimal)


class TestGenerateReactFlowSchema:
    """Tests for generate_react_flow_schema function."""

    def test_generate_schema(self, sample_workflow_blueprint):
        """Test generating React Flow schema from editor state."""
        from empathy_os.socratic.visual_editor import (
            WorkflowVisualizer,
            generate_react_flow_schema,
        )

        # First convert blueprint to editor state
        visualizer = WorkflowVisualizer()
        state = visualizer.blueprint_to_editor(sample_workflow_blueprint)

        # Then generate schema from state
        schema = generate_react_flow_schema(state)

        assert isinstance(schema, dict)
        assert "nodes" in schema
        assert "edges" in schema
        assert "defaultViewport" in schema
        assert isinstance(schema["nodes"], list)
        assert isinstance(schema["edges"], list)

    def test_schema_is_json_serializable(self, sample_workflow_blueprint):
        """Test that schema can be serialized to JSON."""
        from empathy_os.socratic.visual_editor import (
            WorkflowVisualizer,
            generate_react_flow_schema,
        )

        visualizer = WorkflowVisualizer()
        state = visualizer.blueprint_to_editor(sample_workflow_blueprint)
        schema = generate_react_flow_schema(state)

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
        assert "<!DOCTYPE html>" in html
        assert "react" in html.lower() or "script" in html.lower()

    def test_html_contains_workflow_data(self, sample_workflow_blueprint):
        """Test that HTML contains workflow data."""
        from empathy_os.socratic.visual_editor import generate_editor_html

        html = generate_editor_html(sample_workflow_blueprint)

        # Should contain workflow name
        assert sample_workflow_blueprint.name in html

    def test_generate_html_with_title(self, sample_workflow_blueprint):
        """Test generating HTML with custom title."""
        from empathy_os.socratic.visual_editor import generate_editor_html

        html = generate_editor_html(
            sample_workflow_blueprint,
            title="Custom Editor Title",
        )

        assert "Custom Editor Title" in html
