"""Vector Embeddings for Semantic Goal Matching

Provides semantic similarity search for finding similar past goals and their
successful workflow configurations.

Supports multiple embedding backends:
1. Local: Simple TF-IDF based embeddings (no external dependencies)
2. OpenAI: OpenAI's text-embedding-3-small
3. Anthropic: Uses Claude for semantic analysis (via message API)
4. Sentence Transformers: Local neural embeddings (requires torch)

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class EmbeddedGoal:
    """A goal with its embedding vector and metadata."""

    goal_id: str
    goal_text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    domains: list[str] = field(default_factory=list)
    workflow_id: str | None = None
    success_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "goal_id": self.goal_id,
            "goal_text": self.goal_text,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "domains": self.domains,
            "workflow_id": self.workflow_id,
            "success_score": self.success_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmbeddedGoal:
        """Create from dictionary."""
        return cls(
            goal_id=data["goal_id"],
            goal_text=data["goal_text"],
            embedding=data["embedding"],
            metadata=data.get("metadata", {}),
            domains=data.get("domains", []),
            workflow_id=data.get("workflow_id"),
            success_score=data.get("success_score", 0.0),
        )


@dataclass
class SimilarityResult:
    """Result of a similarity search."""

    goal: EmbeddedGoal
    similarity: float
    rank: int


# =============================================================================
# EMBEDDING PROVIDERS
# =============================================================================


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass


class TFIDFEmbeddingProvider(EmbeddingProvider):
    """Simple TF-IDF based embeddings (no external dependencies).

    Uses term frequency-inverse document frequency to create sparse
    embeddings that are then normalized to fixed dimension.
    """

    def __init__(self, dimension: int = 256, vocabulary_size: int = 10000):
        """Initialize TF-IDF provider.

        Args:
            dimension: Output embedding dimension
            vocabulary_size: Maximum vocabulary size
        """
        self._dimension = dimension
        self._vocabulary_size = vocabulary_size
        self._vocabulary: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._document_count = 0

    @property
    def dimension(self) -> int:
        return self._dimension

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words."""
        # Simple tokenization: lowercase, split on non-alphanumeric
        text = text.lower()
        tokens = re.findall(r'\b[a-z][a-z0-9_]*\b', text)
        return tokens

    def _compute_tf(self, tokens: list[str]) -> dict[str, float]:
        """Compute term frequency."""
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        # Normalize by document length
        total = len(tokens) or 1
        return {k: v / total for k, v in tf.items()}

    def _hash_to_bucket(self, term: str) -> int:
        """Hash term to fixed bucket for dimensionality reduction."""
        h = int(hashlib.md5(term.encode()).hexdigest(), 16)
        return h % self._dimension

    def embed(self, text: str) -> list[float]:
        """Generate TF-IDF based embedding.

        Uses feature hashing to project sparse TF-IDF vector
        to fixed dimension.
        """
        tokens = self._tokenize(text)
        tf = self._compute_tf(tokens)

        # Initialize vector
        vector = [0.0] * self._dimension

        # Project TF-IDF scores to fixed dimension using feature hashing
        for term, freq in tf.items():
            bucket = self._hash_to_bucket(term)
            # Use sign trick for better distribution
            sign = 1 if int(hashlib.sha256(term.encode()).hexdigest(), 16) % 2 == 0 else -1
            idf = self._idf.get(term, 1.0)
            vector[bucket] += sign * freq * idf

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        return [self.embed(text) for text in texts]

    def fit(self, documents: list[str]):
        """Fit IDF weights on document corpus.

        Args:
            documents: List of documents to compute IDF from
        """
        self._document_count = len(documents)
        doc_freq: dict[str, int] = {}

        for doc in documents:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                doc_freq[token] = doc_freq.get(token, 0) + 1

        # Compute IDF
        for term, df in doc_freq.items():
            self._idf[term] = math.log((self._document_count + 1) / (df + 1)) + 1


class AnthropicEmbeddingProvider(EmbeddingProvider):
    """Use Claude for semantic embeddings via similarity scoring.

    Note: Anthropic doesn't have a dedicated embedding API, so we use
    Claude to generate semantic feature vectors based on predefined
    aspects relevant to workflow generation.
    """

    ASPECTS = [
        "code review and quality",
        "security and vulnerability",
        "testing and coverage",
        "documentation and comments",
        "performance and optimization",
        "refactoring and cleanup",
        "deployment and CI/CD",
        "debugging and troubleshooting",
        "architecture and design",
        "data processing and ETL",
    ]

    def __init__(self, api_key: str | None = None, dimension: int = 64):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            dimension: Number of semantic aspects to score
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._dimension = min(dimension, len(self.ASPECTS))
        self._client = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None and self.api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("anthropic package not installed")
        return self._client

    def embed(self, text: str) -> list[float]:
        """Generate semantic embedding by scoring relevance to aspects."""
        client = self._get_client()
        if not client:
            # Fallback to TF-IDF
            fallback = TFIDFEmbeddingProvider(dimension=self._dimension)
            return fallback.embed(text)

        aspects = self.ASPECTS[:self._dimension]
        prompt = f"""Rate how relevant this goal is to each aspect on a scale of 0.0 to 1.0.

Goal: "{text}"

Aspects to rate:
{chr(10).join(f'{i+1}. {aspect}' for i, aspect in enumerate(aspects))}

Respond with ONLY a JSON array of numbers, one per aspect, in order.
Example: [0.8, 0.2, 0.5, ...]"""

        try:
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text if response.content else "[]"

            # Parse JSON array
            scores = json.loads(content.strip())
            if isinstance(scores, list) and len(scores) >= self._dimension:
                return [float(s) for s in scores[:self._dimension]]

        except Exception as e:
            logger.warning(f"Anthropic embedding failed: {e}")

        # Fallback
        fallback = TFIDFEmbeddingProvider(dimension=self._dimension)
        return fallback.embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        return [self.embed(text) for text in texts]


class SentenceTransformerProvider(EmbeddingProvider):
    """Use sentence-transformers for local neural embeddings.

    Requires: pip install sentence-transformers
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize sentence transformer.

        Args:
            model_name: HuggingFace model name
        """
        self.model_name = model_name
        self._model = None
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._load_model()
        return self._dimension or 384

    def _load_model(self):
        """Lazy-load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
            except ImportError:
                logger.warning("sentence-transformers not installed")
                self._dimension = 384

    def embed(self, text: str) -> list[float]:
        """Generate embedding using sentence transformer."""
        self._load_model()
        if self._model is None:
            # Fallback to TF-IDF
            fallback = TFIDFEmbeddingProvider(dimension=384)
            return fallback.embed(text)

        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently."""
        self._load_model()
        if self._model is None:
            fallback = TFIDFEmbeddingProvider(dimension=384)
            return [fallback.embed(t) for t in texts]

        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]


# =============================================================================
# VECTOR STORE
# =============================================================================


class VectorStore:
    """In-memory vector store with similarity search.

    Supports persistence to JSON files.
    """

    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        storage_path: Path | str | None = None,
    ):
        """Initialize vector store.

        Args:
            provider: Embedding provider to use
            storage_path: Path to persist vectors
        """
        self.provider = provider or TFIDFEmbeddingProvider()
        self.storage_path = Path(storage_path) if storage_path else None
        self._goals: dict[str, EmbeddedGoal] = {}

        # Load from storage if exists
        if self.storage_path and self.storage_path.exists():
            self._load()

    def add(
        self,
        goal_text: str,
        goal_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        domains: list[str] | None = None,
        workflow_id: str | None = None,
        success_score: float = 0.0,
    ) -> EmbeddedGoal:
        """Add a goal to the store.

        Args:
            goal_text: The goal text
            goal_id: Optional ID (generated if not provided)
            metadata: Optional metadata
            domains: Optional domain tags
            workflow_id: Optional linked workflow ID
            success_score: Success score (0.0-1.0)

        Returns:
            The embedded goal
        """
        if goal_id is None:
            goal_id = hashlib.sha256(goal_text.encode()).hexdigest()[:12]

        embedding = self.provider.embed(goal_text)

        goal = EmbeddedGoal(
            goal_id=goal_id,
            goal_text=goal_text,
            embedding=embedding,
            metadata=metadata or {},
            domains=domains or [],
            workflow_id=workflow_id,
            success_score=success_score,
        )

        self._goals[goal_id] = goal

        # Auto-save if storage configured
        if self.storage_path:
            self._save()

        return goal

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.0,
        domain_filter: str | None = None,
    ) -> list[SimilarityResult]:
        """Search for similar goals.

        Args:
            query: Query text
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            domain_filter: Optional domain to filter by

        Returns:
            List of similarity results sorted by relevance
        """
        if not self._goals:
            return []

        query_embedding = self.provider.embed(query)

        results: list[tuple[float, EmbeddedGoal]] = []

        for goal in self._goals.values():
            # Apply domain filter
            if domain_filter and domain_filter not in goal.domains:
                continue

            similarity = self._cosine_similarity(query_embedding, goal.embedding)
            if similarity >= min_similarity:
                results.append((similarity, goal))

        # Sort by similarity descending
        results.sort(key=lambda x: x[0], reverse=True)

        return [
            SimilarityResult(goal=goal, similarity=sim, rank=i + 1)
            for i, (sim, goal) in enumerate(results[:top_k])
        ]

    def search_by_embedding(
        self,
        embedding: list[float],
        top_k: int = 5,
        min_similarity: float = 0.0,
    ) -> list[SimilarityResult]:
        """Search using pre-computed embedding.

        Args:
            embedding: Pre-computed embedding vector
            top_k: Number of results
            min_similarity: Minimum threshold

        Returns:
            List of similarity results
        """
        results: list[tuple[float, EmbeddedGoal]] = []

        for goal in self._goals.values():
            similarity = self._cosine_similarity(embedding, goal.embedding)
            if similarity >= min_similarity:
                results.append((similarity, goal))

        results.sort(key=lambda x: x[0], reverse=True)

        return [
            SimilarityResult(goal=goal, similarity=sim, rank=i + 1)
            for i, (sim, goal) in enumerate(results[:top_k])
        ]

    def get(self, goal_id: str) -> EmbeddedGoal | None:
        """Get a goal by ID."""
        return self._goals.get(goal_id)

    def remove(self, goal_id: str) -> bool:
        """Remove a goal by ID."""
        if goal_id in self._goals:
            del self._goals[goal_id]
            if self.storage_path:
                self._save()
            return True
        return False

    def update_success_score(self, goal_id: str, score: float):
        """Update the success score for a goal."""
        if goal_id in self._goals:
            self._goals[goal_id].success_score = score
            if self.storage_path:
                self._save()

    def __len__(self) -> int:
        return len(self._goals)

    def __iter__(self) -> Iterator[EmbeddedGoal]:
        return iter(self._goals.values())

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def _save(self):
        """Save to storage."""
        if not self.storage_path:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "goals": [g.to_dict() for g in self._goals.values()],
        }

        with self.storage_path.open("w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        """Load from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with self.storage_path.open("r") as f:
                data = json.load(f)

            for goal_data in data.get("goals", []):
                goal = EmbeddedGoal.from_dict(goal_data)
                self._goals[goal.goal_id] = goal

        except Exception as e:
            logger.warning(f"Failed to load vector store: {e}")


# =============================================================================
# SEMANTIC GOAL MATCHER
# =============================================================================


class SemanticGoalMatcher:
    """High-level API for semantic goal matching.

    Integrates with the Socratic workflow builder to find similar
    past goals and their successful workflow configurations.
    """

    def __init__(
        self,
        provider: str = "tfidf",
        storage_path: Path | str | None = None,
        api_key: str | None = None,
    ):
        """Initialize the matcher.

        Args:
            provider: Embedding provider ("tfidf", "anthropic", "sentence-transformer")
            storage_path: Path to persist vectors
            api_key: API key for cloud providers
        """
        # Default storage path
        if storage_path is None:
            storage_path = Path.home() / ".empathy" / "socratic" / "embeddings.json"

        # Create embedding provider
        if provider == "anthropic":
            embedding_provider = AnthropicEmbeddingProvider(api_key=api_key)
        elif provider == "sentence-transformer":
            embedding_provider = SentenceTransformerProvider()
        else:
            embedding_provider = TFIDFEmbeddingProvider()

        self.store = VectorStore(
            provider=embedding_provider,
            storage_path=storage_path,
        )

    def index_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        domains: list[str] | None = None,
        success_score: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Index a goal for future similarity search.

        Args:
            goal_text: The goal text
            workflow_id: ID of the generated workflow
            domains: Detected domains
            success_score: Success score from execution
            metadata: Additional metadata

        Returns:
            Goal ID
        """
        goal = self.store.add(
            goal_text=goal_text,
            domains=domains,
            workflow_id=workflow_id,
            success_score=success_score,
            metadata=metadata or {},
        )
        return goal.goal_id

    def find_similar(
        self,
        goal_text: str,
        top_k: int = 5,
        min_similarity: float = 0.3,
        min_success_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Find similar past goals.

        Args:
            goal_text: The goal to search for
            top_k: Number of results
            min_similarity: Minimum similarity threshold
            min_success_score: Minimum success score filter

        Returns:
            List of similar goals with their workflows
        """
        results = self.store.search(
            query=goal_text,
            top_k=top_k * 2,  # Get more to filter
            min_similarity=min_similarity,
        )

        # Filter by success score and format results
        formatted = []
        for result in results:
            if result.goal.success_score >= min_success_score:
                formatted.append({
                    "goal_id": result.goal.goal_id,
                    "goal_text": result.goal.goal_text,
                    "similarity": round(result.similarity, 3),
                    "workflow_id": result.goal.workflow_id,
                    "domains": result.goal.domains,
                    "success_score": result.goal.success_score,
                    "metadata": result.goal.metadata,
                })

            if len(formatted) >= top_k:
                break

        return formatted

    def suggest_workflow(
        self,
        goal_text: str,
        min_similarity: float = 0.5,
        min_success_score: float = 0.7,
    ) -> dict[str, Any] | None:
        """Suggest a workflow based on similar successful goals.

        Args:
            goal_text: The goal to find workflow for
            min_similarity: Minimum similarity required
            min_success_score: Minimum success score required

        Returns:
            Best matching workflow suggestion or None
        """
        similar = self.find_similar(
            goal_text=goal_text,
            top_k=1,
            min_similarity=min_similarity,
            min_success_score=min_success_score,
        )

        if similar:
            return similar[0]
        return None

    def update_success(self, goal_id: str, success_score: float):
        """Update success score after workflow execution.

        Args:
            goal_id: Goal ID to update
            success_score: New success score (0.0-1.0)
        """
        self.store.update_success_score(goal_id, success_score)

    @property
    def indexed_count(self) -> int:
        """Number of indexed goals."""
        return len(self.store)
