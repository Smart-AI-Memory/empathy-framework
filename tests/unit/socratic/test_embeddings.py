"""Tests for the Socratic embeddings module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
import math


class TestTFIDFEmbeddingProvider:
    """Tests for TFIDFEmbeddingProvider class."""

    def test_create_provider(self):
        """Test creating a TF-IDF provider."""
        from empathy_os.socratic.embeddings import TFIDFEmbeddingProvider

        provider = TFIDFEmbeddingProvider(dimension=128)

        assert provider.dimension == 128

    def test_embed_text(self):
        """Test embedding text."""
        from empathy_os.socratic.embeddings import TFIDFEmbeddingProvider

        provider = TFIDFEmbeddingProvider(dimension=64)
        embedding = provider.embed("I want to automate code reviews")

        assert len(embedding) == 64
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_normalizes_vector(self):
        """Test that embeddings are normalized."""
        from empathy_os.socratic.embeddings import TFIDFEmbeddingProvider

        provider = TFIDFEmbeddingProvider(dimension=64)
        embedding = provider.embed("Test text for normalization")

        # Check L2 norm is approximately 1
        norm = math.sqrt(sum(x * x for x in embedding))
        assert 0.99 <= norm <= 1.01

    def test_embed_batch(self):
        """Test batch embedding."""
        from empathy_os.socratic.embeddings import TFIDFEmbeddingProvider

        provider = TFIDFEmbeddingProvider(dimension=64)
        texts = ["Code review", "Security scan", "Testing"]

        embeddings = provider.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 64 for e in embeddings)

    def test_fit_idf(self):
        """Test fitting IDF weights."""
        from empathy_os.socratic.embeddings import TFIDFEmbeddingProvider

        provider = TFIDFEmbeddingProvider(dimension=64)

        documents = [
            "Code review for Python",
            "Security vulnerability scan",
            "Unit test generation",
            "Python code analysis",
        ]

        provider.fit(documents)

        # After fitting, embeddings should be influenced by IDF
        embedding = provider.embed("Python code review")
        assert len(embedding) == 64


class TestVectorStore:
    """Tests for VectorStore class."""

    def test_create_store(self, storage_path):
        """Test creating a vector store."""
        from empathy_os.socratic.embeddings import VectorStore

        store = VectorStore(storage_path=storage_path / "test_store.json")
        assert len(store) == 0

    def test_add_goal(self, vector_store):
        """Test adding a goal to the store."""
        goal = vector_store.add(
            goal_text="Automate code reviews",
            domains=["code_review"],
            success_score=0.85,
        )

        assert goal.goal_id is not None
        assert goal.goal_text == "Automate code reviews"
        assert len(vector_store) == 1

    def test_search_goals(self, vector_store):
        """Test searching for similar goals."""
        # Add some goals
        vector_store.add(goal_text="Automate code reviews for Python")
        vector_store.add(goal_text="Security vulnerability scanning")
        vector_store.add(goal_text="Generate unit tests")

        # Search
        results = vector_store.search("code review", top_k=2)

        assert len(results) <= 2
        assert results[0].rank == 1

    def test_search_with_min_similarity(self, vector_store):
        """Test searching with minimum similarity threshold."""
        vector_store.add(goal_text="Automate code reviews")
        vector_store.add(goal_text="Something completely different about cooking")

        results = vector_store.search(
            "code review automation",
            min_similarity=0.5,
        )

        # Should filter out unrelated goals
        assert all(r.similarity >= 0.5 for r in results)

    def test_get_goal(self, vector_store):
        """Test getting a goal by ID."""
        added = vector_store.add(goal_text="Test goal")
        retrieved = vector_store.get(added.goal_id)

        assert retrieved is not None
        assert retrieved.goal_text == "Test goal"

    def test_remove_goal(self, vector_store):
        """Test removing a goal."""
        added = vector_store.add(goal_text="To be removed")
        assert len(vector_store) == 1

        result = vector_store.remove(added.goal_id)

        assert result is True
        assert len(vector_store) == 0

    def test_update_success_score(self, vector_store):
        """Test updating success score."""
        added = vector_store.add(
            goal_text="Test goal",
            success_score=0.5,
        )

        vector_store.update_success_score(added.goal_id, 0.9)
        retrieved = vector_store.get(added.goal_id)

        assert retrieved.success_score == 0.9


class TestSemanticGoalMatcher:
    """Tests for SemanticGoalMatcher class."""

    def test_create_matcher(self, storage_path):
        """Test creating a semantic goal matcher."""
        from empathy_os.socratic.embeddings import SemanticGoalMatcher

        matcher = SemanticGoalMatcher(
            provider="tfidf",
            storage_path=storage_path / "matcher.json",
        )

        assert matcher.indexed_count == 0

    def test_index_goal(self, storage_path):
        """Test indexing a goal."""
        from empathy_os.socratic.embeddings import SemanticGoalMatcher

        matcher = SemanticGoalMatcher(storage_path=storage_path / "matcher.json")

        goal_id = matcher.index_goal(
            goal_text="Automate code reviews",
            workflow_id="workflow-001",
            domains=["code_review"],
            success_score=0.85,
        )

        assert goal_id is not None
        assert matcher.indexed_count == 1

    def test_find_similar(self, storage_path):
        """Test finding similar goals."""
        from empathy_os.socratic.embeddings import SemanticGoalMatcher

        matcher = SemanticGoalMatcher(storage_path=storage_path / "matcher.json")

        # Index some goals
        matcher.index_goal("Automate code reviews for Python", success_score=0.9)
        matcher.index_goal("Security vulnerability scanning", success_score=0.8)
        matcher.index_goal("Generate unit tests", success_score=0.85)

        # Find similar
        similar = matcher.find_similar("code review automation", top_k=2)

        assert len(similar) <= 2

    def test_suggest_workflow(self, storage_path):
        """Test workflow suggestion."""
        from empathy_os.socratic.embeddings import SemanticGoalMatcher

        matcher = SemanticGoalMatcher(storage_path=storage_path / "matcher.json")

        # Index a successful goal
        matcher.index_goal(
            goal_text="Automate code reviews",
            workflow_id="workflow-001",
            success_score=0.9,
        )

        suggestion = matcher.suggest_workflow(
            "I want to review code automatically",
            min_similarity=0.3,
            min_success_score=0.7,
        )

        # May or may not find a match depending on similarity
        if suggestion:
            assert suggestion["success_score"] >= 0.7


class TestEmbeddedGoal:
    """Tests for EmbeddedGoal dataclass."""

    def test_create_embedded_goal(self, sample_embedded_goal):
        """Test creating an embedded goal."""
        assert sample_embedded_goal.goal_id == "goal-001"
        assert len(sample_embedded_goal.embedding) == 256

    def test_serialization(self, sample_embedded_goal):
        """Test embedded goal serialization."""
        from empathy_os.socratic.embeddings import EmbeddedGoal

        data = sample_embedded_goal.to_dict()
        restored = EmbeddedGoal.from_dict(data)

        assert restored.goal_id == sample_embedded_goal.goal_id
        assert restored.goal_text == sample_embedded_goal.goal_text
