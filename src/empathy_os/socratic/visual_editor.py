"""Visual Workflow Editor

Provides a visual editor for modifying generated workflow blueprints.
Supports both terminal-based visualization and web-based React components.

Features:
- ASCII art workflow visualization for terminal
- Drag-and-drop capable React schemas
- Agent configuration panels
- Stage dependency editing
- Real-time validation

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .blueprint import StageSpec, WorkflowBlueprint

# =============================================================================
# DATA STRUCTURES
# =============================================================================


class NodeType(Enum):
    """Types of nodes in the visual editor."""

    AGENT = "agent"
    STAGE = "stage"
    START = "start"
    END = "end"
    CONNECTOR = "connector"


@dataclass
class Position:
    """Position in the visual editor."""

    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}


@dataclass
class EditorNode:
    """A node in the visual editor."""

    node_id: str
    node_type: str | NodeType  # Accept both string and enum
    label: str
    position: dict[str, int] | Position  # Accept both dict and Position
    data: dict[str, Any] = field(default_factory=dict)
    selected: bool = False
    locked: bool = False

    def to_dict(self) -> dict[str, Any]:
        # Handle both string and enum for node_type
        node_type_str = self.node_type.value if isinstance(self.node_type, NodeType) else self.node_type
        # Handle both dict and Position for position
        pos_dict = self.position.to_dict() if isinstance(self.position, Position) else self.position
        return {
            "id": self.node_id,
            "type": node_type_str,
            "data": {"label": self.label, **self.data},
            "position": pos_dict,
            "selected": self.selected,
            "locked": self.locked,
        }


@dataclass
class EditorEdge:
    """An edge (connection) in the visual editor."""

    edge_id: str
    source: str  # Source node ID
    target: str  # Target node ID
    label: str = ""
    animated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "animated": self.animated,
        }


@dataclass
class EditorState:
    """State of the visual editor."""

    workflow_id: str = ""  # ID of the workflow being edited
    nodes: list[EditorNode] = field(default_factory=list)
    edges: list[EditorEdge] = field(default_factory=list)
    selected_node_id: str | None = None
    zoom: float = 1.0
    pan_x: int = 0
    pan_y: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "selectedNodeId": self.selected_node_id,
            "zoom": self.zoom,
            "panX": self.pan_x,
            "panY": self.pan_y,
        }

    def to_react_flow(self) -> dict[str, Any]:
        """Convert state to React Flow schema format.

        Returns:
            Dict with 'nodes' and 'edges' arrays for React Flow
        """
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


# =============================================================================
# WORKFLOW TO EDITOR CONVERSION
# =============================================================================


class WorkflowVisualizer:
    """Converts workflow blueprints to visual editor state."""

    def __init__(self, node_spacing: int = 200, stage_spacing: int = 150):
        """Initialize visualizer.

        Args:
            node_spacing: Horizontal spacing between nodes
            stage_spacing: Vertical spacing between stages
        """
        self.node_spacing = node_spacing
        self.stage_spacing = stage_spacing

    def blueprint_to_editor(self, blueprint: WorkflowBlueprint) -> EditorState:
        """Convert a workflow blueprint to editor state.

        Args:
            blueprint: The workflow blueprint

        Returns:
            EditorState ready for visualization
        """
        nodes: list[EditorNode] = []
        edges: list[EditorEdge] = []

        # Create agent lookup (agents are AgentBlueprint objects with .spec attribute)
        agents_by_id = {a.spec.id: a for a in blueprint.agents}

        # Create start node
        start_node = EditorNode(
            node_id="start",
            node_type=NodeType.START,
            label="Start",
            position=Position(x=400, y=50),
            locked=True,
        )
        nodes.append(start_node)

        # Process stages
        y_offset = 150
        first_stage = True

        for stage in blueprint.stages:
            # Create stage node
            stage_node = EditorNode(
                node_id=stage.id,
                node_type=NodeType.STAGE,
                label=stage.name,
                position=Position(x=400, y=y_offset),
                data={
                    "parallel": stage.parallel,
                    "timeout": stage.timeout,
                },
            )
            nodes.append(stage_node)

            # Connect from start or dependencies
            if first_stage:
                edges.append(EditorEdge(
                    edge_id=f"start->{stage.id}",
                    source="start",
                    target=stage.id,
                    animated=True,
                ))
                first_stage = False
            else:
                for dep in stage.depends_on:
                    edges.append(EditorEdge(
                        edge_id=f"{dep}->{stage.id}",
                        source=dep,
                        target=stage.id,
                    ))

            # Create agent nodes for this stage
            agent_x_start = 200
            for i, agent_id in enumerate(stage.agent_ids):
                agent_bp = agents_by_id.get(agent_id)
                if not agent_bp:
                    continue

                agent_node = EditorNode(
                    node_id=agent_id,
                    node_type=NodeType.AGENT,
                    label=agent_bp.spec.name,
                    position=Position(
                        x=agent_x_start + (i * self.node_spacing),
                        y=y_offset + 60,
                    ),
                    data={
                        "role": agent_bp.spec.role.value,
                        "tools": [t.id for t in agent_bp.spec.tools],
                        "goal": agent_bp.spec.goal,
                    },
                )
                nodes.append(agent_node)

                # Connect stage to agent
                edges.append(EditorEdge(
                    edge_id=f"{stage.id}->{agent_id}",
                    source=stage.id,
                    target=agent_id,
                ))

            y_offset += self.stage_spacing

        # Create end node
        end_node = EditorNode(
            node_id="end",
            node_type=NodeType.END,
            label="End",
            position=Position(x=400, y=y_offset),
            locked=True,
        )
        nodes.append(end_node)

        # Connect last stage to end
        if blueprint.stages:
            last_stage = blueprint.stages[-1]
            edges.append(EditorEdge(
                edge_id=f"{last_stage.id}->end",
                source=last_stage.id,
                target="end",
                animated=True,
            ))

        return EditorState(workflow_id=blueprint.id, nodes=nodes, edges=edges)

    def from_blueprint(self, blueprint: WorkflowBlueprint) -> EditorState:
        """Alias for blueprint_to_editor - converts blueprint to editor state."""
        return self.blueprint_to_editor(blueprint)

    def to_blueprint(
        self, state: EditorState, original_blueprint: WorkflowBlueprint | None = None
    ) -> WorkflowBlueprint:
        """Alias for editor_to_blueprint - converts editor state back to blueprint."""
        if original_blueprint is None:
            # Create minimal blueprint for reconstruction
            from .blueprint import WorkflowBlueprint
            original_blueprint = WorkflowBlueprint(
                id=state.workflow_id,
                name="Reconstructed Workflow",
                description="Reconstructed from editor state",
                domain="general",
            )
        return self.editor_to_blueprint(state, original_blueprint)

    def editor_to_blueprint(
        self,
        state: EditorState,
        original_blueprint: WorkflowBlueprint,
    ) -> WorkflowBlueprint:
        """Convert editor state back to workflow blueprint.

        Args:
            state: The editor state
            original_blueprint: Original blueprint for reference

        Returns:
            Updated WorkflowBlueprint
        """
        # Extract stage nodes and their agents
        stage_nodes = [n for n in state.nodes if n.node_type == NodeType.STAGE]
        agent_nodes = [n for n in state.nodes if n.node_type == NodeType.AGENT]

        # Build edge lookup
        edges_by_source: dict[str, list[str]] = {}
        edges_by_target: dict[str, list[str]] = {}
        for edge in state.edges:
            edges_by_source.setdefault(edge.source, []).append(edge.target)
            edges_by_target.setdefault(edge.target, []).append(edge.source)

        # Rebuild stages
        new_stages: list[StageSpec] = []
        for stage_node in stage_nodes:
            # Find agents connected to this stage
            agent_ids = [
                target
                for target in edges_by_source.get(stage_node.node_id, [])
                if any(a.node_id == target and a.node_type == NodeType.AGENT for a in agent_nodes)
            ]

            # Find dependencies (stages that connect TO this stage)
            dependencies = [
                source
                for source in edges_by_target.get(stage_node.node_id, [])
                if source != "start" and any(
                    s.node_id == source and s.node_type == NodeType.STAGE
                    for s in stage_nodes
                )
            ]

            new_stages.append(StageSpec(
                id=stage_node.node_id,
                name=stage_node.label,
                description=stage_node.data.get("description", f"Stage: {stage_node.label}"),
                agent_ids=agent_ids,
                depends_on=dependencies,
                parallel=stage_node.data.get("parallel", False),
                timeout=stage_node.data.get("timeout"),
            ))

        # Update blueprint
        return WorkflowBlueprint(
            id=original_blueprint.id,
            name=original_blueprint.name,
            description=original_blueprint.description,
            domain=original_blueprint.domain,
            agents=original_blueprint.agents,
            stages=new_stages,
            generated_at=original_blueprint.generated_at,
        )


# =============================================================================
# ASCII VISUALIZATION
# =============================================================================


class ASCIIVisualizer:
    """Creates ASCII art visualization of workflows for terminal display."""

    def __init__(self, width: int = 80):
        """Initialize ASCII visualizer.

        Args:
            width: Maximum width in characters
        """
        self.width = width

    def render(self, blueprint: WorkflowBlueprint) -> str:
        """Render workflow as ASCII art.

        Args:
            blueprint: The workflow blueprint

        Returns:
            ASCII art string
        """
        lines: list[str] = []

        # Header
        lines.append("=" * self.width)
        lines.append(self._center(f"Workflow: {blueprint.name}"))
        lines.append("=" * self.width)
        lines.append("")

        # Agents summary
        lines.append(self._box("Agents"))
        for agent in blueprint.agents:
            # Access tools via spec since AgentBlueprint wraps AgentSpec
            agent_tools = agent.spec.tools if hasattr(agent, "spec") else []
            tools = ", ".join(t.id for t in agent_tools[:3])
            if len(agent_tools) > 3:
                tools += f" (+{len(agent_tools) - 3} more)"
            agent_role = agent.spec.role if hasattr(agent, "spec") else agent.role
            agent_name = agent.spec.name if hasattr(agent, "spec") else agent.name
            lines.append(f"  [{agent_role.value[:3].upper()}] {agent_name}")
            lines.append(f"       Tools: {tools}")
        lines.append("")

        # Flow diagram
        lines.append(self._box("Workflow Flow"))
        lines.append("")
        lines.append(self._center("[ START ]"))
        lines.append(self._center("│"))

        for i, stage in enumerate(blueprint.stages):
            is_last = i == len(blueprint.stages) - 1

            # Stage box
            stage_line = f"┌{'─' * (len(stage.name) + 2)}┐"
            lines.append(self._center(stage_line))
            lines.append(self._center(f"│ {stage.name} │"))
            lines.append(self._center(f"└{'─' * (len(stage.name) + 2)}┘"))

            # Agents in stage
            if stage.agent_ids:
                agent_str = " → ".join(stage.agent_ids)
                if len(agent_str) > self.width - 10:
                    agent_str = agent_str[:self.width - 13] + "..."
                lines.append(self._center(f"({agent_str})"))

            # Connector
            if not is_last:
                lines.append(self._center("│"))
                if blueprint.stages[i + 1].parallel:
                    lines.append(self._center("║ (parallel)"))
                else:
                    lines.append(self._center("│"))

        lines.append(self._center("│"))
        lines.append(self._center("[ END ]"))
        lines.append("")

        # Footer
        lines.append("=" * self.width)

        return "\n".join(lines)

    def render_compact(self, blueprint: WorkflowBlueprint) -> str:
        """Render a compact single-line representation.

        Args:
            blueprint: The workflow blueprint

        Returns:
            Compact string representation
        """
        stages = []
        for stage in blueprint.stages:
            agents = ",".join(a[:8] for a in stage.agent_ids)
            marker = "∥" if stage.parallel else "→"
            stages.append(f"[{stage.name}{marker}:{agents}]")

        return f" {' → '.join(stages)} "

    def _center(self, text: str) -> str:
        """Center text within width."""
        if len(text) >= self.width:
            return text
        padding = (self.width - len(text)) // 2
        return " " * padding + text

    def _box(self, title: str) -> str:
        """Create a section header box."""
        return f"┌─ {title} {'─' * (self.width - len(title) - 5)}┐"


# =============================================================================
# REACT COMPONENT SCHEMAS
# =============================================================================


def generate_react_flow_schema(state: EditorState) -> dict[str, Any]:
    """Generate React Flow compatible schema.

    Args:
        state: Editor state

    Returns:
        Schema for React Flow library
    """
    # Node types for React Flow
    node_type_map = {
        NodeType.START: "input",
        NodeType.END: "output",
        NodeType.STAGE: "default",
        NodeType.AGENT: "default",
    }

    # Node styles
    node_styles = {
        NodeType.START: {
            "background": "#10b981",
            "color": "white",
            "border": "2px solid #059669",
            "borderRadius": "50%",
            "width": 80,
            "height": 80,
        },
        NodeType.END: {
            "background": "#ef4444",
            "color": "white",
            "border": "2px solid #dc2626",
            "borderRadius": "50%",
            "width": 80,
            "height": 80,
        },
        NodeType.STAGE: {
            "background": "#3b82f6",
            "color": "white",
            "border": "2px solid #2563eb",
            "borderRadius": "8px",
            "padding": "10px",
        },
        NodeType.AGENT: {
            "background": "#8b5cf6",
            "color": "white",
            "border": "2px solid #7c3aed",
            "borderRadius": "8px",
            "padding": "8px",
        },
    }

    nodes = []
    for node in state.nodes:
        rf_node = {
            "id": node.node_id,
            "type": node_type_map.get(node.node_type, "default"),
            "position": node.position.to_dict(),
            "data": {
                "label": node.label,
                **node.data,
            },
            "style": node_styles.get(node.node_type, {}),
            "draggable": not node.locked,
            "selectable": True,
        }
        nodes.append(rf_node)

    edges = []
    for edge in state.edges:
        rf_edge = {
            "id": edge.edge_id,
            "source": edge.source,
            "target": edge.target,
            "label": edge.label,
            "animated": edge.animated,
            "style": {"strokeWidth": 2},
            "markerEnd": {"type": "arrowclosed"},
        }
        edges.append(rf_edge)

    return {
        "nodes": nodes,
        "edges": edges,
        "defaultViewport": {
            "x": state.pan_x,
            "y": state.pan_y,
            "zoom": state.zoom,
        },
    }


def generate_editor_html(
    blueprint: WorkflowBlueprint,
    title: str = "Workflow Editor",
) -> str:
    """Generate standalone HTML page with workflow editor.

    Args:
        blueprint: The workflow blueprint
        title: Page title

    Returns:
        Complete HTML page
    """
    visualizer = WorkflowVisualizer()
    state = visualizer.blueprint_to_editor(blueprint)
    react_schema = generate_react_flow_schema(state)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/reactflow@11/dist/umd/index.js"></script>
    <link href="https://unpkg.com/reactflow@11/dist/style.css" rel="stylesheet" />
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, -apple-system, sans-serif; }}
        #root {{ width: 100vw; height: 100vh; }}
        .react-flow__node {{ font-size: 12px; }}
        .react-flow__edge-path {{ stroke-width: 2; }}

        .panel {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
        }}

        .panel h3 {{
            margin-bottom: 10px;
            font-size: 14px;
            color: #374151;
        }}

        .panel p {{
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 5px;
        }}

        .export-btn {{
            margin-top: 10px;
            padding: 8px 16px;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}

        .export-btn:hover {{ background: #2563eb; }}
    </style>
</head>
<body>
    <div id="root"></div>
    <script>
        const {{ useState, useCallback }} = React;
        const {{ ReactFlow, Background, Controls, MiniMap }} = window.ReactFlow;

        const initialNodes = {json.dumps(react_schema['nodes'], indent=2)};
        const initialEdges = {json.dumps(react_schema['edges'], indent=2)};

        function WorkflowEditor() {{
            const [nodes, setNodes] = useState(initialNodes);
            const [edges, setEdges] = useState(initialEdges);
            const [selectedNode, setSelectedNode] = useState(null);

            const onNodesChange = useCallback((changes) => {{
                setNodes((nds) => {{
                    return nds.map((node) => {{
                        const change = changes.find(c => c.id === node.id);
                        if (change && change.type === 'position' && change.position) {{
                            return {{ ...node, position: change.position }};
                        }}
                        return node;
                    }});
                }});
            }}, []);

            const onNodeClick = useCallback((event, node) => {{
                setSelectedNode(node);
            }}, []);

            const exportWorkflow = () => {{
                const data = {{ nodes, edges }};
                const blob = new Blob([JSON.stringify(data, null, 2)], {{ type: 'application/json' }});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'workflow.json';
                a.click();
            }};

            return React.createElement('div', {{ style: {{ width: '100%', height: '100%' }} }},
                React.createElement(ReactFlow, {{
                    nodes: nodes,
                    edges: edges,
                    onNodesChange: onNodesChange,
                    onNodeClick: onNodeClick,
                    fitView: true,
                }},
                    React.createElement(Background, null),
                    React.createElement(Controls, null),
                    React.createElement(MiniMap, null)
                ),
                React.createElement('div', {{ className: 'panel' }},
                    React.createElement('h3', null, '{blueprint.name}'),
                    React.createElement('p', null, 'Agents: {len(blueprint.agents)}'),
                    React.createElement('p', null, 'Stages: {len(blueprint.stages)}'),
                    selectedNode && React.createElement('div', null,
                        React.createElement('hr', {{ style: {{ margin: '10px 0' }} }}),
                        React.createElement('p', null, 'Selected: ' + selectedNode.data.label),
                        selectedNode.data.role && React.createElement('p', null, 'Role: ' + selectedNode.data.role),
                        selectedNode.data.tools && React.createElement('p', null, 'Tools: ' + selectedNode.data.tools.length)
                    ),
                    React.createElement('button', {{
                        className: 'export-btn',
                        onClick: exportWorkflow
                    }}, 'Export JSON')
                )
            );
        }}

        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(React.createElement(WorkflowEditor));
    </script>
</body>
</html>"""


# =============================================================================
# VISUAL EDITOR CLASS
# =============================================================================


class VisualWorkflowEditor:
    """High-level API for visual workflow editing."""

    def __init__(self):
        """Initialize the editor."""
        self.visualizer = WorkflowVisualizer()
        self.ascii_visualizer = ASCIIVisualizer()

    def create_editor_state(self, blueprint: WorkflowBlueprint) -> EditorState:
        """Create editor state from blueprint.

        Args:
            blueprint: The workflow blueprint

        Returns:
            EditorState for the editor
        """
        return self.visualizer.blueprint_to_editor(blueprint)

    def apply_changes(
        self,
        state: EditorState,
        original_blueprint: WorkflowBlueprint,
    ) -> WorkflowBlueprint:
        """Apply editor changes to create updated blueprint.

        Args:
            state: Modified editor state
            original_blueprint: Original blueprint

        Returns:
            Updated WorkflowBlueprint
        """
        return self.visualizer.editor_to_blueprint(state, original_blueprint)

    def render_ascii(self, blueprint: WorkflowBlueprint) -> str:
        """Render workflow as ASCII art.

        Args:
            blueprint: The workflow blueprint

        Returns:
            ASCII art visualization
        """
        return self.ascii_visualizer.render(blueprint)

    def render_compact(self, blueprint: WorkflowBlueprint) -> str:
        """Render compact representation.

        Args:
            blueprint: The workflow blueprint

        Returns:
            Compact string
        """
        return self.ascii_visualizer.render_compact(blueprint)

    def generate_html_editor(self, blueprint: WorkflowBlueprint) -> str:
        """Generate HTML page with interactive editor.

        Args:
            blueprint: The workflow blueprint

        Returns:
            Complete HTML page
        """
        return generate_editor_html(blueprint)

    def generate_react_schema(self, blueprint: WorkflowBlueprint) -> dict[str, Any]:
        """Generate React Flow compatible schema.

        Args:
            blueprint: The workflow blueprint

        Returns:
            React Flow schema
        """
        state = self.visualizer.blueprint_to_editor(blueprint)
        return generate_react_flow_schema(state)

    def validate_state(self, state: EditorState) -> list[str]:
        """Validate editor state for errors.

        Args:
            state: The editor state

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []

        # Check for required nodes
        has_start = any(n.node_type == NodeType.START for n in state.nodes)
        has_end = any(n.node_type == NodeType.END for n in state.nodes)

        if not has_start:
            errors.append("Workflow must have a start node")
        if not has_end:
            errors.append("Workflow must have an end node")

        # Check for orphan nodes (no connections)
        node_ids = {n.node_id for n in state.nodes}
        connected_nodes: set[str] = set()
        for edge in state.edges:
            connected_nodes.add(edge.source)
            connected_nodes.add(edge.target)

        orphans = node_ids - connected_nodes - {"start", "end"}
        if orphans:
            errors.append(f"Orphan nodes (not connected): {', '.join(orphans)}")

        # Check for cycles (simple detection)
        # Note: A more robust implementation would use DFS
        visited: set[str] = set()
        def check_cycle(node_id: str, path: set[str]) -> bool:
            if node_id in path:
                return True
            if node_id in visited:
                return False

            visited.add(node_id)
            path.add(node_id)

            for edge in state.edges:
                if edge.source == node_id:
                    if check_cycle(edge.target, path.copy()):
                        return True

            return False

        if check_cycle("start", set()):
            errors.append("Workflow contains a cycle")

        return errors
