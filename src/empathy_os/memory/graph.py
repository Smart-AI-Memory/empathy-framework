"""Memory Graph - Cross-Wizard Knowledge Base

A knowledge graph that connects findings across all wizards,
enabling intelligent correlation and learning.

Features:
- Add findings from any wizard as nodes
- Connect related findings with typed edges
- Query for similar past findings
- Traverse relationships to find root causes

Storage: JSON file in patterns/ directory

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

import hashlib
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path

from .edges import REVERSE_EDGE_TYPES, Edge, EdgeType
from .nodes import Node, NodeType


class MemoryGraph:
    """Knowledge graph for cross-wizard intelligence.

    Stores nodes (findings) and edges (relationships) discovered
    by wizards, enabling pattern correlation across sessions.

    Usage:
        graph = MemoryGraph()

        # Add a bug finding
        bug_id = graph.add_finding(
            wizard="bug-predict",
            finding={
                "type": "bug",
                "name": "Null reference in auth.py",
                "description": "Missing null check on user object",
                "file": "src/auth.py",
                "line": 42,
                "severity": "high"
            }
        )

        # Connect to a fix
        fix_id = graph.add_finding(
            wizard="bug-predict",
            finding={
                "type": "fix",
                "name": "Add null check",
                "description": "Added guard clause for user object"
            }
        )
        graph.add_edge(bug_id, fix_id, EdgeType.FIXED_BY)

        # Find similar bugs
        similar = graph.find_similar({"name": "Null reference"})
    """

    def __init__(self, path: str | Path = "patterns/memory_graph.json"):
        """Initialize the memory graph.

        Args:
            path: Path to JSON storage file

        """
        self.path = Path(path)
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

        # Indexes for fast lookup
        self._edges_by_source: dict[str, list[Edge]] = defaultdict(list)
        self._edges_by_target: dict[str, list[Edge]] = defaultdict(list)
        self._nodes_by_type: dict[NodeType, list[str]] = defaultdict(list)
        self._nodes_by_wizard: dict[str, list[str]] = defaultdict(list)
        self._nodes_by_file: dict[str, list[str]] = defaultdict(list)

        self._load()

    def _load(self) -> None:
        """Load graph from JSON file."""
        if not self.path.exists():
            # Ensure directory exists
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._save()
            return

        try:
            with open(self.path) as f:
                data = json.load(f)

            # Load nodes
            for node_data in data.get("nodes", []):
                node = Node.from_dict(node_data)
                self.nodes[node.id] = node
                self._index_node(node)

            # Load edges
            for edge_data in data.get("edges", []):
                edge = Edge.from_dict(edge_data)
                self.edges.append(edge)
                self._index_edge(edge)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load graph from {self.path}: {e}")
            self.nodes = {}
            self.edges = []

    def _save(self) -> None:
        """Save graph to JSON file."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        validated_path = _validate_file_path(str(self.path))
        with open(validated_path, "w") as f:
            json.dump(data, f, indent=2)

    def _index_node(self, node: Node) -> None:
        """Add node to indexes."""
        self._nodes_by_type[node.type].append(node.id)
        if node.source_wizard:
            self._nodes_by_wizard[node.source_wizard].append(node.id)
        if node.source_file:
            self._nodes_by_file[node.source_file].append(node.id)

    def _index_edge(self, edge: Edge) -> None:
        """Add edge to indexes."""
        self._edges_by_source[edge.source_id].append(edge)
        self._edges_by_target[edge.target_id].append(edge)

    def _generate_id(self, finding: dict[str, Any]) -> str:
        """Generate unique ID for a finding."""
        # Create hash from content
        content = json.dumps(finding, sort_keys=True)
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{finding.get('type', 'node')}_{timestamp}_{hash_val}"

    def add_finding(self, wizard: str, finding: dict[str, Any]) -> str:
        """Add a finding from any wizard, return node ID.

        Args:
            wizard: Name of the wizard adding this finding
            finding: Dict with at least 'type' and 'name' keys

        Returns:
            Node ID for the created node

        Example:
            node_id = graph.add_finding(
                wizard="security-audit",
                finding={
                    "type": "vulnerability",
                    "name": "SQL Injection in query builder",
                    "description": "User input not sanitized",
                    "file": "src/db/query.py",
                    "line": 156,
                    "severity": "critical"
                }
            )

        """
        node_id = self._generate_id(finding)

        # Map finding type to NodeType
        type_str = finding.get("type", "pattern")
        try:
            node_type = NodeType(type_str)
        except ValueError:
            node_type = NodeType.PATTERN

        node = Node(
            id=node_id,
            type=node_type,
            name=finding.get("name", "Unnamed finding"),
            description=finding.get("description", ""),
            source_wizard=wizard,
            source_file=finding.get("file", finding.get("source_file", "")),
            source_line=finding.get("line", finding.get("source_line")),
            severity=finding.get("severity", ""),
            confidence=finding.get("confidence", 1.0),
            metadata=finding.get("metadata", {}),
            tags=finding.get("tags", []),
        )

        self.nodes[node_id] = node
        self._index_node(node)
        self._save()

        return node_id

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        description: str = "",
        wizard: str = "",
        weight: float = 1.0,
        bidirectional: bool = False,
    ) -> str:
        """Add an edge between two nodes.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            edge_type: Type of relationship
            description: Optional description of the relationship
            wizard: Wizard that created this edge
            weight: Strength of relationship (0.0 - 1.0)
            bidirectional: If True, also create reverse edge

        Returns:
            Edge ID

        """
        if source_id not in self.nodes:
            raise ValueError(f"Source node not found: {source_id}")
        if target_id not in self.nodes:
            raise ValueError(f"Target node not found: {target_id}")

        edge = Edge(
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
            description=description,
            source_wizard=wizard,
            weight=weight,
        )

        self.edges.append(edge)
        self._index_edge(edge)

        # Optionally create reverse edge
        if bidirectional and edge_type in REVERSE_EDGE_TYPES:
            reverse_type = REVERSE_EDGE_TYPES[edge_type]
            reverse_edge = Edge(
                source_id=target_id,
                target_id=source_id,
                type=reverse_type,
                description=description,
                source_wizard=wizard,
                weight=weight,
            )
            self.edges.append(reverse_edge)
            self._index_edge(reverse_edge)

        self._save()
        return edge.id

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def find_related(
        self,
        node_id: str,
        edge_types: list[EdgeType] | None = None,
        direction: str = "outgoing",
        max_depth: int = 1,
    ) -> list[Node]:
        """Find related nodes via specified edge types.

        Args:
            node_id: Starting node ID
            edge_types: List of edge types to follow (None = all)
            direction: "outgoing", "incoming", or "both"
            max_depth: Maximum traversal depth

        Returns:
            List of related nodes

        """
        if node_id not in self.nodes:
            return []

        visited: set[str] = {node_id}
        result: list[Node] = []
        current_level: set[str] = {node_id}

        for _ in range(max_depth):
            next_level: set[str] = set()

            for current_id in current_level:
                edges_to_check: list[Edge] = []

                if direction in ("outgoing", "both"):
                    edges_to_check.extend(self._edges_by_source.get(current_id, []))
                if direction in ("incoming", "both"):
                    edges_to_check.extend(self._edges_by_target.get(current_id, []))

                for edge in edges_to_check:
                    if edge_types and edge.type not in edge_types:
                        continue

                    # Get the other node
                    other_id = edge.target_id if edge.source_id == current_id else edge.source_id

                    if other_id not in visited:
                        visited.add(other_id)
                        next_level.add(other_id)
                        if other_id in self.nodes:
                            result.append(self.nodes[other_id])

            if not next_level:
                break
            current_level = next_level

        return result

    def find_similar(
        self,
        finding: dict[str, Any],
        threshold: float = 0.5,
        limit: int = 10,
    ) -> list[tuple[Node, float]]:
        """Find similar past findings.

        Uses simple text similarity on name and description.

        Args:
            finding: Dict with 'name' and/or 'description'
            threshold: Minimum similarity score (0.0 - 1.0)
            limit: Maximum results to return

        Returns:
            List of (node, similarity_score) tuples

        """
        query_name = finding.get("name", "").lower()
        query_desc = finding.get("description", "").lower()
        query_type = finding.get("type")
        query_file = finding.get("file", "")

        results: list[tuple[Node, float]] = []

        for node in self.nodes.values():
            score = 0.0
            factors = 0.0

            # Name similarity (word overlap)
            if query_name and node.name:
                name_words = set(query_name.split())
                node_words = set(node.name.lower().split())
                if name_words and node_words:
                    overlap = len(name_words & node_words)
                    union = len(name_words | node_words)
                    score += (overlap / union) * 0.5
                    factors += 0.5

            # Description similarity
            if query_desc and node.description:
                desc_words = set(query_desc.split())
                node_words = set(node.description.lower().split())
                if desc_words and node_words:
                    overlap = len(desc_words & node_words)
                    union = len(desc_words | node_words)
                    score += (overlap / union) * 0.3
                    factors += 0.3

            # Type match bonus
            if query_type:
                try:
                    if node.type == NodeType(query_type):
                        score += 0.15
                        factors += 0.15
                except ValueError:
                    pass

            # File match bonus
            if query_file and node.source_file:
                if query_file == node.source_file:
                    score += 0.05
                    factors += 0.05

            # Normalize
            if factors > 0:
                score = score / factors

            if score >= threshold:
                results.append((node, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def find_by_type(self, node_type: NodeType) -> list[Node]:
        """Find all nodes of a specific type."""
        node_ids = self._nodes_by_type.get(node_type, [])
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def find_by_wizard(self, wizard: str) -> list[Node]:
        """Find all nodes created by a specific wizard."""
        node_ids = self._nodes_by_wizard.get(wizard, [])
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def find_by_file(self, file_path: str) -> list[Node]:
        """Find all nodes related to a specific file."""
        node_ids = self._nodes_by_file.get(file_path, [])
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def get_path(
        self,
        source_id: str,
        target_id: str,
        edge_types: list[EdgeType] | None = None,
        max_depth: int = 5,
    ) -> list[tuple[Node, Edge | None]]:
        """Find a path between two nodes using BFS.

        Args:
            source_id: Starting node ID
            target_id: Target node ID
            edge_types: Edge types to traverse (None = all)
            max_depth: Maximum path length

        Returns:
            List of (node, edge_to_node) tuples representing the path

        """
        if source_id not in self.nodes or target_id not in self.nodes:
            return []

        # BFS with path tracking (deque for O(1) popleft)
        visited: set[str] = {source_id}
        queue: deque[list[tuple[str, Edge | None]]] = deque([[(source_id, None)]])

        while queue:
            path = queue.popleft()
            current_id = path[-1][0]

            if len(path) > max_depth:
                continue

            if current_id == target_id:
                return [(self.nodes[nid], edge) for nid, edge in path]

            for edge in self._edges_by_source.get(current_id, []):
                if edge_types and edge.type not in edge_types:
                    continue
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    new_path = path + [(edge.target_id, edge)]
                    queue.append(new_path)

        return []

    def get_statistics(self) -> dict[str, Any]:
        """Get graph statistics."""
        type_counts: dict[str, int] = defaultdict(int)
        wizard_counts: dict[str, int] = defaultdict(int)
        severity_counts: dict[str, int] = defaultdict(int)

        for node in self.nodes.values():
            type_counts[node.type.value] += 1
            if node.source_wizard:
                wizard_counts[node.source_wizard] += 1
            if node.severity:
                severity_counts[node.severity] += 1

        edge_type_counts: dict[str, int] = defaultdict(int)
        for edge in self.edges:
            edge_type_counts[edge.type.value] += 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_type": dict(type_counts),
            "nodes_by_wizard": dict(wizard_counts),
            "nodes_by_severity": dict(severity_counts),
            "edges_by_type": dict(edge_type_counts),
            "unique_files": len(self._nodes_by_file),
        }

    def update_node(self, node_id: str, updates: dict[str, Any]) -> bool:
        """Update a node's properties.

        Args:
            node_id: Node to update
            updates: Dict of properties to update

        Returns:
            True if updated, False if node not found

        """
        if node_id not in self.nodes:
            return False

        node = self.nodes[node_id]

        if "status" in updates:
            node.status = updates["status"]
        if "description" in updates:
            node.description = updates["description"]
        if "severity" in updates:
            node.severity = updates["severity"]
        if "tags" in updates:
            node.tags = updates["tags"]
        if "metadata" in updates:
            node.metadata.update(updates["metadata"])

        node.updated_at = datetime.now()
        self._save()
        return True

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its connected edges.

        Args:
            node_id: Node to delete

        Returns:
            True if deleted, False if not found

        """
        if node_id not in self.nodes:
            return False

        # Remove from indexes
        node = self.nodes[node_id]
        if node.type in self._nodes_by_type:
            self._nodes_by_type[node.type] = [
                nid for nid in self._nodes_by_type[node.type] if nid != node_id
            ]
        if node.source_wizard in self._nodes_by_wizard:
            self._nodes_by_wizard[node.source_wizard] = [
                nid for nid in self._nodes_by_wizard[node.source_wizard] if nid != node_id
            ]
        if node.source_file in self._nodes_by_file:
            self._nodes_by_file[node.source_file] = [
                nid for nid in self._nodes_by_file[node.source_file] if nid != node_id
            ]

        # Remove connected edges
        self.edges = [e for e in self.edges if e.source_id != node_id and e.target_id != node_id]
        if node_id in self._edges_by_source:
            del self._edges_by_source[node_id]
        if node_id in self._edges_by_target:
            del self._edges_by_target[node_id]

        # Remove node
        del self.nodes[node_id]
        self._save()
        return True

    def clear(self) -> None:
        """Clear all nodes and edges."""
        self.nodes = {}
        self.edges = []
        self._edges_by_source = defaultdict(list)
        self._edges_by_target = defaultdict(list)
        self._nodes_by_type = defaultdict(list)
        self._nodes_by_wizard = defaultdict(list)
        self._nodes_by_file = defaultdict(list)
        self._save()
