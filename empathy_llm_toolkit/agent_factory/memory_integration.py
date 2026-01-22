"""Memory-Aware Agent Wrapper

Integrates agents with the Memory Graph for cross-agent learning.
Agents can query for similar past findings and store new findings
for other agents to benefit from.

Usage:
    from empathy_llm_toolkit.agent_factory import AgentFactory
    from empathy_llm_toolkit.agent_factory.memory_integration import MemoryAwareAgent

    factory = AgentFactory()
    agent = factory.create_agent(
        name="bug_hunter",
        role="debugger",
        memory_graph_enabled=True
    )

    # Agent will automatically:
    # 1. Query similar past bugs before invocation
    # 2. Store new findings after invocation

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import logging
from typing import Any

from empathy_llm_toolkit.agent_factory.base import BaseAgent

logger = logging.getLogger(__name__)


class MemoryAwareAgent(BaseAgent):
    """Agent wrapper that integrates with Memory Graph.

    Enables cross-agent learning by:
    - Querying similar past findings before invocation
    - Storing new findings after invocation
    - Connecting findings across agents
    """

    def __init__(
        self,
        agent: BaseAgent,
        graph_path: str = "patterns/memory_graph.json",
        store_findings: bool = True,
        query_similar: bool = True,
        similarity_threshold: float = 0.4,
        max_similar_results: int = 5,
    ):
        """Initialize memory-aware agent wrapper.

        Args:
            agent: The underlying agent to wrap
            graph_path: Path to memory graph JSON file
            store_findings: Whether to store findings in memory graph
            query_similar: Whether to query for similar findings
            similarity_threshold: Minimum similarity score for results
            max_similar_results: Maximum similar findings to return

        """
        super().__init__(agent.config)
        self._wrapped = agent
        self._graph_path = graph_path
        self._store_findings = store_findings
        self._query_similar = query_similar
        self._similarity_threshold = similarity_threshold
        self._max_similar_results = max_similar_results
        self._graph: Any = None

        self._init_graph()

    def _init_graph(self) -> None:
        """Initialize connection to Memory Graph."""
        try:
            from empathy_os.memory import MemoryGraph

            self._graph = MemoryGraph(path=self._graph_path)
            logger.debug(f"Memory graph loaded from {self._graph_path}")
        except ImportError:
            logger.warning("empathy_os.memory not available, memory integration disabled")
        except Exception as e:
            logger.warning(f"Failed to load memory graph: {e}")

    async def invoke(self, input_data: str | dict, context: dict | None = None) -> dict:
        """Invoke the agent with memory graph integration.

        1. Query for similar past findings
        2. Add context from similar findings
        3. Invoke wrapped agent
        4. Store any new findings

        Args:
            input_data: User input or structured data
            context: Optional context (previous results, shared state)

        Returns:
            Dict with at least {"output": str, "metadata": dict}

        """
        context = context or {}

        # 1. Query for similar findings if enabled
        if self._query_similar and self._graph:
            similar_findings = self._get_similar_findings(input_data)
            if similar_findings:
                context["similar_findings"] = similar_findings
                context["memory_graph_hits"] = len(similar_findings)

        # 2. Invoke wrapped agent with enhanced context
        result = await self._wrapped.invoke(input_data, context)

        # 3. Store findings if enabled
        if self._store_findings and self._graph:
            self._store_agent_findings(input_data, result)

        # 4. Add memory graph metadata
        if "metadata" not in result:
            result["metadata"] = {}

        result["metadata"]["memory_graph"] = {
            "enabled": self._graph is not None,
            "similar_found": len(context.get("similar_findings", [])),
            "findings_stored": self._store_findings,
            "graph_path": self._graph_path,
        }

        return result

    async def stream(self, input_data: str | dict, context: dict | None = None):
        """Stream agent response with memory integration.

        Note: Memory integration for streaming works at the full response
        level - similar findings are added to context before streaming starts.
        """
        context = context or {}

        # Query for similar findings
        if self._query_similar and self._graph:
            similar_findings = self._get_similar_findings(input_data)
            if similar_findings:
                context["similar_findings"] = similar_findings

        # Stream from wrapped agent
        async for chunk in self._wrapped.stream(input_data, context):  # type: ignore[attr-defined]
            yield chunk

    def _get_similar_findings(self, input_data: str | dict) -> list[dict]:
        """Query memory graph for similar past findings."""
        if not self._graph:
            return []

        try:
            # Build query from input
            if isinstance(input_data, str):
                query = {"name": input_data[:100], "description": input_data}
            else:
                query = {
                    "name": str(input_data.get("task", input_data.get("input", "")))[:100],
                    "description": str(input_data),
                }

            # Query graph
            similar = self._graph.find_similar(
                query,
                threshold=self._similarity_threshold,
                limit=self._max_similar_results,
            )

            # Format results
            results = []
            for node, score in similar:
                if score >= self._similarity_threshold:
                    finding = {
                        "name": node.name,
                        "type": node.type.value if node.type else None,
                        "similarity": round(score, 2),
                        "source_wizard": node.source_wizard,
                        "metadata": node.metadata or {},
                    }

                    # Check for resolutions
                    resolutions = self._get_resolutions(node.id)
                    if resolutions:
                        finding["resolutions"] = resolutions

                    results.append(finding)

            if results:
                logger.debug(f"Found {len(results)} similar findings for agent {self.name}")

            return results

        except Exception as e:
            logger.warning(f"Error querying similar findings: {e}")
            return []

    def _get_resolutions(self, node_id: str) -> list[dict]:
        """Get resolutions (fixes) for a finding."""
        if not self._graph:
            return []

        try:
            from empathy_os.memory import EdgeType

            related = self._graph.find_related(node_id, [EdgeType.FIXED_BY])
            return [
                {
                    "name": r.name,
                    "description": r.metadata.get("description", ""),
                }
                for r in related
            ]
        except Exception:  # noqa: BLE001
            # INTENTIONAL: Graceful degradation when graph unavailable
            logger.debug(f"Could not get resolutions for node {node_id}")
            return []

    def _store_agent_findings(self, input_data: str | dict, result: dict) -> None:
        """Store findings from agent result in memory graph."""
        if not self._graph:
            return

        try:
            metadata = result.get("metadata", {})

            # Check for explicit findings in result
            findings = metadata.get("findings", [])

            # Also check for bug/issue/vulnerability patterns in output
            if not findings and self._contains_finding_patterns(result.get("output", "")):
                # Create implicit finding from result
                if isinstance(input_data, str):
                    task_name = input_data[:100]
                else:
                    task_name = str(input_data.get("task", input_data.get("input", "")))[:100]

                findings = [
                    {
                        "type": self._infer_finding_type(result.get("output", "")),
                        "name": f"{self.name}: {task_name}",
                        "description": result.get("output", "")[:500],
                    },
                ]

            # Store findings
            for finding in findings:
                finding_id = self._graph.add_finding(self.name, finding)
                logger.debug(f"Stored finding {finding_id} from agent {self.name}")

            # Save graph
            if findings:
                self._graph._save()

        except Exception as e:
            logger.warning(f"Error storing findings: {e}")

    def _contains_finding_patterns(self, text: str) -> bool:
        """Check if output contains patterns indicating a finding."""
        patterns = [
            "found",
            "detected",
            "issue",
            "bug",
            "error",
            "vulnerability",
            "problem",
            "warning",
            "fix",
        ]
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in patterns)

    def _infer_finding_type(self, text: str) -> str:
        """Infer finding type from output text."""
        text_lower = text.lower()

        # Check for fix/resolution first (takes precedence)
        if any(x in text_lower for x in ["fix", "fixed", "resolved", "patched"]):
            return "fix"
        if any(x in text_lower for x in ["vulnerability", "security", "injection", "xss"]):
            return "vulnerability"
        if any(x in text_lower for x in ["bug", "error", "exception", "crash"]):
            return "bug"
        if any(x in text_lower for x in ["performance", "slow", "latency", "memory"]):
            return "performance_issue"
        return "pattern"

    # Delegate other methods to wrapped agent
    def add_tool(self, tool: Any) -> None:
        """Add a tool to the wrapped agent."""
        self._wrapped.add_tool(tool)

    def get_conversation_history(self) -> list[dict]:
        """Get conversation history from wrapped agent."""
        return self._wrapped.get_conversation_history()

    def clear_history(self) -> None:
        """Clear conversation history in wrapped agent."""
        self._wrapped.clear_history()

    @property
    def model(self) -> str:
        """Get the model being used by wrapped agent."""
        return self._wrapped.model

    @property
    def graph(self):
        """Get the memory graph instance."""
        return self._graph

    def get_graph_stats(self) -> dict:
        """Get statistics from memory graph."""
        if not self._graph:
            return {"enabled": False}

        try:
            return {
                "enabled": True,
                "node_count": len(self._graph.nodes),
                "edge_count": len(self._graph.edges),
                "path": str(self._graph.path),
            }
        except Exception as e:  # noqa: BLE001
            # INTENTIONAL: Stats are optional, don't crash on errors
            logger.debug(f"Could not get graph stats: {e}")
            return {"enabled": True, "error": "Could not get stats"}
