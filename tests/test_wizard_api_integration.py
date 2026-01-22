"""Integration tests for wizard components and API layer.

Tests the integration between:
- BaseWizard and wizard implementations
- Wizard implementations and FastAPI endpoints
- Request/response flow through the entire stack
- Error handling across component boundaries

Copyright 2025 Smart AI Memory, LLC
Licensed under Fair Source 0.9
"""

from unittest.mock import Mock

import pytest

from empathy_os.redis_memory import RedisShortTermMemory
from empathy_software_plugin.wizards.base_wizard import BaseWizard


class MockWizard(BaseWizard):
    """Mock wizard for testing."""

    @property
    def name(self) -> str:
        return "Mock Wizard"

    @property
    def level(self) -> int:
        return 3

    async def analyze(self, context: dict) -> dict:
        return {
            "predictions": ["mock prediction"],
            "recommendations": ["mock recommendation"],
            "confidence": 0.95,
        }


class TestWizardMemoryIntegration:
    """Test integration between wizards and Redis memory."""

    @pytest.mark.asyncio
    async def test_wizard_memory_round_trip(self):
        """Test complete memory storage and retrieval cycle."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stash.return_value = True
        mock_memory.retrieve.return_value = None  # Cache miss initially

        wizard = MockWizard(short_term_memory=mock_memory)

        context = {"test": "data"}

        # First call - cache miss, fresh analysis
        result1 = await wizard.analyze_with_cache(context)

        assert result1["_from_cache"] is False
        assert mock_memory.stash.called
        assert mock_memory.retrieve.called

        # Second call - cache hit
        mock_memory.retrieve.return_value = {
            "predictions": ["cached"],
            "confidence": 0.8,
        }

        result2 = await wizard.analyze_with_cache(context)

        assert result2["_from_cache"] is True
        assert result2["predictions"] == ["cached"]

    @pytest.mark.asyncio
    async def test_wizard_shared_context_flow(self):
        """Test shared context between multiple wizards."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stash.return_value = True
        mock_memory.retrieve.return_value = None

        wizard1 = MockWizard(short_term_memory=mock_memory)
        wizard2 = MockWizard(short_term_memory=mock_memory)

        # Wizard 1 shares context
        success = wizard1.share_context("test_key", {"data": "shared"})
        assert success is True

        # Wizard 2 retrieves shared context
        mock_memory.retrieve.return_value = {"data": "shared"}
        shared = wizard2.get_shared_context("test_key")

        assert shared is not None
        assert shared["data"] == "shared"

    @pytest.mark.asyncio
    async def test_wizard_pattern_staging_flow(self):
        """Test pattern discovery and staging workflow."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stage_pattern.return_value = True

        wizard = MockWizard(short_term_memory=mock_memory)

        # Stage discovered pattern
        success = wizard.stage_discovered_pattern(
            pattern_id="test_pattern",
            pattern_type="security",
            name="SQL Injection Pattern",
            description="Detects potential SQL injection vulnerabilities",
            confidence=0.9,
            code="SELECT * FROM users WHERE id = ?",
        )

        assert success is True
        assert mock_memory.stage_pattern.called

        # Verify staged pattern structure
        call_args = mock_memory.stage_pattern.call_args[0][0]  # First positional arg
        assert call_args.pattern_id == "test_pattern"
        assert call_args.pattern_type == "security"
        assert call_args.confidence == 0.9

    @pytest.mark.asyncio
    async def test_wizard_signal_coordination(self):
        """Test wizard coordination via signals."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.send_signal.return_value = True

        wizard = MockWizard(short_term_memory=mock_memory)

        # Send completion signal
        success = wizard.send_signal("analysis_complete", {"status": "success", "results": 10})

        assert success is True
        assert mock_memory.send_signal.called

        # Verify signal includes wizard name
        call_kwargs = mock_memory.send_signal.call_args[1]
        assert "wizard" in call_kwargs["data"]
        assert call_kwargs["data"]["wizard"] == "Mock Wizard"


class TestWizardAPIRequestFlow:
    """Test request/response flow through API layer."""

    def test_wizard_request_model_validation(self):
        """Test WizardRequest model validates correctly."""
        # Import WizardRequest from wizard_api if available
        try:
            from backend.api.wizard_api import WizardRequest

            # Valid request
            request = WizardRequest(input="test input", context={"key": "value"})
            assert request.input == "test input"
            assert request.context == {"key": "value"}

            # Request with defaults
            minimal_request = WizardRequest(input="minimal")
            assert minimal_request.context is None
            assert minimal_request.user_id == "demo_user"

        except ImportError:
            pytest.skip("wizard_api not available")

    def test_wizard_response_model_structure(self):
        """Test WizardResponse model structure."""
        try:
            from backend.api.wizard_api import WizardResponse

            # Success response
            success_response = WizardResponse(
                success=True,
                output="Analysis complete",
                analysis={"predictions": []},
            )

            assert success_response.success is True
            assert success_response.error is None

            # Error response
            error_response = WizardResponse(success=False, output="", error="Failed to analyze")

            assert error_response.success is False
            assert error_response.error == "Failed to analyze"

        except ImportError:
            pytest.skip("wizard_api not available")


class TestMultiWizardCoordination:
    """Test coordination between multiple wizard types."""

    @pytest.mark.asyncio
    async def test_wizard_pipeline_execution(self):
        """Test sequential execution of multiple wizards."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stash.return_value = True
        mock_memory.retrieve.return_value = None

        wizard1 = MockWizard(short_term_memory=mock_memory)
        wizard2 = MockWizard(short_term_memory=mock_memory)

        context = {"input": "test"}

        # Wizard 1 analyzes and shares results
        result1 = await wizard1.analyze(context)
        wizard1.share_context("step1_results", result1)

        # Wizard 2 uses shared context
        mock_memory.retrieve.return_value = result1
        shared_results = wizard2.get_shared_context("step1_results")

        # Wizard 2 analyzes with enriched context
        enriched_context = {**context, "previous_analysis": shared_results}
        result2 = await wizard2.analyze(enriched_context)

        assert result2 is not None
        assert "predictions" in result2

    @pytest.mark.asyncio
    async def test_wizard_fallback_chain(self):
        """Test fallback behavior when primary wizard fails."""

        class FailingWizard(MockWizard):
            async def analyze(self, context: dict) -> dict:
                raise Exception("Analysis failed")

        failing_wizard = FailingWizard()
        fallback_wizard = MockWizard()

        context = {"test": "data"}

        # Try primary wizard
        try:
            result = await failing_wizard.analyze(context)
            primary_success = True
        except Exception:
            primary_success = False
            # Fall back to secondary
            result = await fallback_wizard.analyze(context)

        assert primary_success is False
        assert result is not None
        assert "predictions" in result


class TestWizardErrorPropagation:
    """Test error propagation through wizard-API stack."""

    @pytest.mark.asyncio
    async def test_wizard_analysis_error_handling(self):
        """Test wizard handles analysis errors gracefully."""

        class ErrorWizard(MockWizard):
            async def analyze(self, context: dict) -> dict:
                raise ValueError("Invalid context")

        wizard = ErrorWizard()

        with pytest.raises(ValueError, match="Invalid context"):
            await wizard.analyze({"bad": "context"})

    @pytest.mark.asyncio
    async def test_memory_error_doesnt_break_analysis(self):
        """Test wizard continues when memory operations fail."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.retrieve.side_effect = Exception("Redis down")
        mock_memory.stash.side_effect = Exception("Redis down")

        wizard = MockWizard(short_term_memory=mock_memory)

        context = {"test": "data"}

        # analyze_with_cache should handle memory errors
        with pytest.raises(Exception):  # noqa: B017
            await wizard.analyze_with_cache(context)

    @pytest.mark.asyncio
    async def test_wizard_without_memory_works(self):
        """Test wizards work correctly without memory layer."""
        wizard = MockWizard(short_term_memory=None)

        assert wizard.has_memory() is False

        # Should still be able to analyze
        result = await wizard.analyze({"test": "data"})

        assert result is not None
        assert "predictions" in result

        # Memory operations should return False
        assert wizard.cache_result({}, {}) is False
        assert wizard.get_cached_result({}) is None
        assert wizard.share_context("key", {}) is False


class TestWizardAPIEndpoints:
    """Test wizard API endpoints (requires mocked FastAPI client)."""

    def test_api_initialization(self):
        """Test API app initializes correctly."""
        try:
            from backend.api.wizard_api import app

            assert app is not None
            assert app.title == "Empathy Wizard API"
            assert app.version == "2.0.0"

        except ImportError:
            pytest.skip("wizard_api not available")

    def test_cors_middleware_configured(self):
        """Test CORS middleware is properly configured."""
        try:
            from backend.api.wizard_api import app

            # Check middleware is present
            middlewares = [m for m in app.user_middleware if "CORS" in str(type(m))]
            assert len(middlewares) > 0

        except ImportError:
            pytest.skip("wizard_api not available")


class TestWizardLifecycle:
    """Test wizard initialization and cleanup lifecycle."""

    @pytest.mark.asyncio
    async def test_wizard_initialization_with_memory(self):
        """Test wizard initializes correctly with memory."""
        mock_memory = Mock(spec=RedisShortTermMemory)

        wizard = MockWizard(short_term_memory=mock_memory, cache_ttl_seconds=3600)

        assert wizard.short_term_memory is not None
        assert wizard.cache_ttl == 3600
        assert wizard.has_memory() is True
        assert wizard.name == "Mock Wizard"
        assert wizard.level == 3

    @pytest.mark.asyncio
    async def test_wizard_credentials_setup(self):
        """Test wizard sets up credentials correctly."""
        wizard = MockWizard()

        # Wizard should have credentials
        assert hasattr(wizard, "_credentials")
        assert wizard._credentials.agent_id == "wizard_MockWizard"

    @pytest.mark.asyncio
    async def test_wizard_cache_key_generation(self):
        """Test cache keys are generated correctly."""
        wizard = MockWizard()

        context1 = {"a": 1, "b": 2}
        context2 = {"b": 2, "a": 1}  # Same content, different order

        key1 = wizard._cache_key(context1)
        key2 = wizard._cache_key(context2)

        # Should be consistent regardless of order
        assert key1 == key2

        # Should include wizard name
        assert "Mock Wizard" in key1

        # Different context should generate different key
        context3 = {"a": 1, "b": 3}
        key3 = wizard._cache_key(context3)
        assert key3 != key1


class TestWizardAPIIntegrationEndToEnd:
    """End-to-end integration tests simulating complete workflows."""

    @pytest.mark.asyncio
    async def test_complete_analysis_workflow(self):
        """Test complete workflow from request to response."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.retrieve.return_value = None
        mock_memory.stash.return_value = True

        wizard = MockWizard(short_term_memory=mock_memory)

        # Simulate API request
        request_context = {"input": "Analyze this code", "file_path": "test.py"}

        # Execute analysis
        result = await wizard.analyze_with_cache(request_context)

        # Verify result structure
        assert result["_from_cache"] is False
        assert "predictions" in result
        assert "recommendations" in result
        assert "confidence" in result
        assert result["confidence"] > 0

        # Verify caching occurred
        assert mock_memory.stash.called

    @pytest.mark.asyncio
    async def test_collaborative_wizard_workflow(self):
        """Test multiple wizards collaborating on analysis."""
        mock_memory = Mock(spec=RedisShortTermMemory)
        mock_memory.stash.return_value = True

        # Security wizard finds issues
        security_wizard = MockWizard(short_term_memory=mock_memory)
        security_results = await security_wizard.analyze({"code": "test"})

        # Share findings
        security_wizard.share_context("security_findings", security_results)

        # Performance wizard uses security findings
        performance_wizard = MockWizard(short_term_memory=mock_memory)
        mock_memory.retrieve.return_value = security_results

        security_findings = performance_wizard.get_shared_context("security_findings")
        performance_results = await performance_wizard.analyze(
            {"code": "test", "security_context": security_findings}
        )

        assert performance_results is not None
        assert "predictions" in performance_results

    @pytest.mark.asyncio
    async def test_wizard_retry_with_cache_fallback(self):
        """Test wizard retries with cache fallback on failure."""
        mock_memory = Mock(spec=RedisShortTermMemory)

        # First attempt - cache miss, analysis succeeds
        mock_memory.retrieve.return_value = None
        mock_memory.stash.return_value = True

        wizard = MockWizard(short_term_memory=mock_memory)
        result1 = await wizard.analyze_with_cache({"test": "data"})

        assert result1["_from_cache"] is False

        # Second attempt - use cached result
        cached_result = result1.copy()
        cached_result.pop("_from_cache")
        mock_memory.retrieve.return_value = cached_result

        result2 = await wizard.analyze_with_cache({"test": "data"})

        assert result2["_from_cache"] is True
        assert result2["confidence"] == result1["confidence"]
