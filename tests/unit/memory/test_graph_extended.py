"""Extended tests for memory graph system.

These tests cover additional functionality not in test_memory_graph.py:
- Node creation and serialization
- Edge creation and reverse types
- Graph traversal algorithms
- Similarity search
- Statistics and metrics
- Error handling
"""


import pytest

from empathy_os.memory.edges import REVERSE_EDGE_TYPES, Edge, EdgeType
from empathy_os.memory.graph import MemoryGraph
from empathy_os.memory.nodes import BugNode, Node, NodeType, VulnerabilityNode


@pytest.mark.unit
class TestNodeCreation:
    """Test Node dataclass creation and methods."""

    def test_create_node_with_required_fields(self):
        """Test creating node with required fields."""
        node = Node(
            id="node_001",
            type=NodeType.BUG,
            name="Test Bug",
        )

        assert node.id == "node_001"
        assert node.type == NodeType.BUG
        assert node.name == "Test Bug"

    def test_node_default_values(self):
        """Test node default field values."""
        node = Node(id="n", type=NodeType.BUG, name="Test")

        assert node.description == ""
        assert node.source_wizard == ""
        assert node.confidence == 1.0
        assert node.status == "open"
        assert node.tags == []
        assert node.metadata == {}

    def test_node_to_dict(self):
        """Test node serialization to dict."""
        node = Node(
            id="n1",
            type=NodeType.VULNERABILITY,
            name="SQL Injection",
            severity="high",
            tags=["security", "database"],
        )

        result = node.to_dict()

        assert result["id"] == "n1"
        assert result["type"] == "vulnerability"  # lowercase enum value
        assert result["name"] == "SQL Injection"
        assert result["severity"] == "high"
        assert "security" in result["tags"]

    def test_node_from_dict(self):
        """Test node deserialization from dict."""
        data = {
            "id": "n2",
            "type": "bug",  # lowercase enum value
            "name": "Memory Leak",
            "severity": "medium",
            "confidence": 0.85,
        }

        node = Node.from_dict(data)

        assert node.id == "n2"
        assert node.type == NodeType.BUG
        assert node.name == "Memory Leak"
        assert node.confidence == 0.85


@pytest.mark.unit
class TestSpecializedNodes:
    """Test specialized node types."""

    def test_bug_node_extra_fields(self):
        """Test BugNode has extra fields."""
        node = BugNode(
            id="bug_001",
            type=NodeType.BUG,
            name="Null Pointer",
            root_cause="Missing null check",
            fix_suggestion="Add if statement",
        )

        assert node.root_cause == "Missing null check"
        assert node.fix_suggestion == "Add if statement"

    def test_vulnerability_node_extra_fields(self):
        """Test VulnerabilityNode has extra fields."""
        node = VulnerabilityNode(
            id="vuln_001",
            type=NodeType.VULNERABILITY,
            name="XSS",
            cwe_id="CWE-79",
            cvss_score=7.5,
        )

        assert node.cwe_id == "CWE-79"
        assert node.cvss_score == 7.5


@pytest.mark.unit
class TestEdgeCreation:
    """Test Edge dataclass creation."""

    def test_create_edge(self):
        """Test creating edge between nodes."""
        edge = Edge(
            source_id="node_a",
            target_id="node_b",
            type=EdgeType.CAUSES,
        )

        assert edge.source_id == "node_a"
        assert edge.target_id == "node_b"
        assert edge.type == EdgeType.CAUSES

    def test_edge_id_property(self):
        """Test edge ID generation."""
        edge = Edge(
            source_id="src",
            target_id="tgt",
            type=EdgeType.FIXES,
        )

        assert "src" in edge.id
        assert "tgt" in edge.id
        assert "FIXES" in edge.id or "fixes" in edge.id.lower()

    def test_edge_to_dict(self):
        """Test edge serialization."""
        edge = Edge(
            source_id="a",
            target_id="b",
            type=EdgeType.RELATED_TO,
            weight=0.8,
            description="Related findings",
        )

        result = edge.to_dict()

        assert result["source_id"] == "a"
        assert result["target_id"] == "b"
        assert result["weight"] == 0.8

    def test_reverse_edge_types_mapping(self):
        """Test REVERSE_EDGE_TYPES has correct mappings."""
        assert REVERSE_EDGE_TYPES.get(EdgeType.CAUSES) == EdgeType.CAUSED_BY
        assert REVERSE_EDGE_TYPES.get(EdgeType.FIXES) == EdgeType.FIXED_BY
        assert REVERSE_EDGE_TYPES.get(EdgeType.CONTAINS) == EdgeType.CONTAINED_IN


@pytest.mark.unit
class TestMemoryGraphBasicOperations:
    """Test basic MemoryGraph operations."""

    @pytest.fixture
    def graph(self, tmp_path):
        """Create a fresh graph for each test."""
        return MemoryGraph(path=tmp_path / "test_graph.json")

    def _add_finding(self, graph, node_type, name, **kwargs):
        """Helper to add a finding using correct API."""
        finding = {"type": node_type.value, "name": name, **kwargs}
        return graph.add_finding("test-wizard", finding)

    def test_empty_graph(self, graph):
        """Test empty graph initialization."""
        stats = graph.get_statistics()

        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0

    def test_add_finding_creates_node(self, graph):
        """Test add_finding creates a new node."""
        finding = {
            "type": "bug",
            "name": "Test Bug",
            "description": "A test bug for testing",
            "severity": "high",
        }
        node_id = graph.add_finding("bug-predict", finding)

        assert node_id is not None
        node = graph.get_node(node_id)
        assert node is not None
        assert node.name == "Test Bug"

    def test_add_edge_connects_nodes(self, graph):
        """Test add_edge connects two nodes."""
        id1 = graph.add_finding("test", {"type": "bug", "name": "Bug 1"})
        id2 = graph.add_finding("test", {"type": "fix", "name": "Fix 1"})

        edge_id = graph.add_edge(
            source_id=id1,
            target_id=id2,
            edge_type=EdgeType.FIXED_BY,
        )

        assert edge_id is not None

    def test_get_nonexistent_node_returns_none(self, graph):
        """Test getting nonexistent node returns None."""
        node = graph.get_node("nonexistent_id")

        assert node is None

    def test_delete_node_removes_node(self, graph):
        """Test delete_node removes node."""
        node_id = graph.add_finding("test", {"type": "bug", "name": "Delete Me"})

        result = graph.delete_node(node_id)

        assert result is True
        assert graph.get_node(node_id) is None

    def test_delete_node_removes_connected_edges(self, graph):
        """Test delete_node also removes connected edges."""
        id1 = graph.add_finding("test", {"type": "bug", "name": "Bug"})
        id2 = graph.add_finding("test", {"type": "fix", "name": "Fix"})
        graph.add_edge(source_id=id1, target_id=id2, edge_type=EdgeType.FIXED_BY)

        graph.delete_node(id1)

        # Edge should be gone too
        related = graph.find_related(id2)
        assert len(related) == 0

    def test_update_node_modifies_properties(self, graph):
        """Test update_node modifies node properties."""
        node_id = graph.add_finding("test", {"type": "bug", "name": "Original", "status": "open"})

        result = graph.update_node(node_id, {"status": "resolved", "severity": "low"})

        assert result is True
        node = graph.get_node(node_id)
        assert node.status == "resolved"
        assert node.severity == "low"

    def test_clear_removes_all(self, graph):
        """Test clear removes all nodes and edges."""
        graph.add_finding("test", {"type": "bug", "name": "Bug 1"})
        graph.add_finding("test", {"type": "bug", "name": "Bug 2"})

        graph.clear()

        stats = graph.get_statistics()
        assert stats["total_nodes"] == 0


@pytest.mark.unit
class TestMemoryGraphTraversal:
    """Test graph traversal methods."""

    @pytest.fixture
    def graph_with_nodes(self, tmp_path):
        """Create graph with test nodes."""
        graph = MemoryGraph(path=tmp_path / "traversal_test.json")

        # Create a chain: Bug -> causes -> Vulnerability -> causes -> Performance
        bug_id = graph.add_finding("test", {"type": "bug", "name": "Root Bug"})
        vuln_id = graph.add_finding("test", {"type": "vulnerability", "name": "Vuln"})
        perf_id = graph.add_finding("test", {"type": "performance_issue", "name": "Slow"})

        graph.add_edge(bug_id, vuln_id, EdgeType.CAUSES)
        graph.add_edge(vuln_id, perf_id, EdgeType.CAUSES)

        return graph, bug_id, vuln_id, perf_id

    def test_find_related_outgoing(self, graph_with_nodes):
        """Test find_related with outgoing edges."""
        graph, bug_id, vuln_id, perf_id = graph_with_nodes

        related = graph.find_related(bug_id, direction="outgoing", max_depth=1)

        assert len(related) == 1
        assert related[0].id == vuln_id

    def test_find_related_with_depth(self, graph_with_nodes):
        """Test find_related traverses multiple levels."""
        graph, bug_id, vuln_id, perf_id = graph_with_nodes

        related = graph.find_related(bug_id, direction="outgoing", max_depth=2)

        assert len(related) == 2  # vuln and perf

    def test_find_related_with_edge_filter(self, graph_with_nodes):
        """Test find_related with edge type filter."""
        graph, bug_id, vuln_id, perf_id = graph_with_nodes

        # Add a different edge type
        fix_id = graph.add_finding("test", {"type": "fix", "name": "Fix"})
        graph.add_edge(bug_id, fix_id, EdgeType.FIXED_BY)

        # Filter to only CAUSES edges
        related = graph.find_related(
            bug_id, direction="outgoing", edge_types=[EdgeType.CAUSES]
        )

        ids = [n.id for n in related]
        assert vuln_id in ids
        assert fix_id not in ids

    def test_get_path_finds_shortest_path(self, graph_with_nodes):
        """Test get_path finds shortest path."""
        graph, bug_id, vuln_id, perf_id = graph_with_nodes

        path = graph.get_path(bug_id, perf_id)

        assert len(path) == 3  # bug -> vuln -> perf
        assert path[0][0].id == bug_id
        assert path[-1][0].id == perf_id

    def test_get_path_no_connection(self, tmp_path):
        """Test get_path returns empty for disconnected nodes."""
        graph = MemoryGraph(path=tmp_path / "disconnected.json")

        id1 = graph.add_finding("test", {"type": "bug", "name": "Isolated 1"})
        id2 = graph.add_finding("test", {"type": "bug", "name": "Isolated 2"})

        path = graph.get_path(id1, id2)

        assert path == []


@pytest.mark.unit
class TestMemoryGraphSearch:
    """Test graph search methods."""

    @pytest.fixture
    def graph_with_types(self, tmp_path):
        """Create graph with various node types."""
        graph = MemoryGraph(path=tmp_path / "search_test.json")

        graph.add_finding("bug-predict", {"type": "bug", "name": "Memory Leak"})
        graph.add_finding("bug-predict", {"type": "bug", "name": "Null Pointer"})
        graph.add_finding("security-audit", {"type": "vulnerability", "name": "SQL Injection"})
        graph.add_finding("perf-audit", {"type": "performance_issue", "name": "Slow Query"})

        return graph

    def test_find_by_type(self, graph_with_types):
        """Test find_by_type filters correctly."""
        bugs = graph_with_types.find_by_type(NodeType.BUG)

        assert len(bugs) == 2
        assert all(b.type == NodeType.BUG for b in bugs)

    def test_find_by_wizard(self, graph_with_types):
        """Test find_by_wizard filters correctly."""
        findings = graph_with_types.find_by_wizard("bug-predict")

        assert len(findings) == 2

    def test_find_similar_returns_matches(self, graph_with_types):
        """Test find_similar returns similar nodes."""
        # Use lower threshold since similarity is based on word overlap
        results = graph_with_types.find_similar(
            {"name": "Memory Leak Bug", "description": "Leak in memory"},
            threshold=0.3
        )

        # Should find "Memory Leak" as similar
        assert len(results) > 0
        names = [r[0].name for r in results]
        assert "Memory Leak" in names

    def test_find_similar_with_threshold(self, graph_with_types):
        """Test find_similar respects threshold."""
        results = graph_with_types.find_similar(
            {"name": "Completely Different"}, threshold=0.9
        )

        # High threshold should filter out weak matches
        assert len(results) == 0


@pytest.mark.unit
class TestMemoryGraphStatistics:
    """Test graph statistics methods."""

    @pytest.fixture
    def graph_with_data(self, tmp_path):
        """Create graph with various data."""
        graph = MemoryGraph(path=tmp_path / "stats_test.json")

        # Add nodes with various severities (lowercase type values)
        graph.add_finding("test", {"type": "bug", "name": "Bug 1", "severity": "high"})
        graph.add_finding("test", {"type": "bug", "name": "Bug 2", "severity": "high"})
        graph.add_finding("test", {"type": "bug", "name": "Bug 3", "severity": "medium"})
        graph.add_finding("test", {"type": "vulnerability", "name": "Vuln 1", "severity": "critical"})

        return graph

    def test_get_statistics_node_counts(self, graph_with_data):
        """Test statistics includes node counts."""
        stats = graph_with_data.get_statistics()

        assert stats["total_nodes"] == 4
        assert stats["nodes_by_type"]["bug"] == 3  # lowercase keys
        assert stats["nodes_by_type"]["vulnerability"] == 1

    def test_get_statistics_severity_distribution(self, graph_with_data):
        """Test statistics includes severity distribution."""
        stats = graph_with_data.get_statistics()

        assert "nodes_by_severity" in stats
        assert stats["nodes_by_severity"]["high"] == 2
        assert stats["nodes_by_severity"]["critical"] == 1


@pytest.mark.unit
class TestMemoryGraphPersistence:
    """Test graph persistence."""

    def test_save_and_load(self, tmp_path):
        """Test graph persists to disk."""
        path = tmp_path / "persist_test.json"

        # Create and save
        graph1 = MemoryGraph(path=path)
        graph1.add_finding("test", {"type": "bug", "name": "Persistent Bug"})
        graph1._save()

        # Load in new instance
        graph2 = MemoryGraph(path=path)

        stats = graph2.get_statistics()
        assert stats["total_nodes"] == 1

    def test_auto_save_on_modification(self, tmp_path):
        """Test graph auto-saves on modification."""
        path = tmp_path / "autosave_test.json"

        graph = MemoryGraph(path=path)
        graph.add_finding("test", {"type": "bug", "name": "Auto Saved"})

        # File should exist
        assert path.exists()
