"""Batch Processing Workflow using Anthropic Batch API.

Enables 50% cost reduction by processing non-urgent tasks asynchronously.
Batch API processes requests within 24 hours - not suitable for interactive workflows.

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from empathy_llm_toolkit.providers import AnthropicBatchProvider
from empathy_os.config import _validate_file_path
from empathy_os.models import get_model

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """Single request in a batch."""

    task_id: str
    task_type: str
    input_data: dict[str, Any]
    model_tier: str = "capable"  # cheap, capable, premium


@dataclass
class BatchResult:
    """Result from batch processing."""

    task_id: str
    success: bool
    output: dict[str, Any] | None = None
    error: str | None = None


class BatchProcessingWorkflow:
    """Process multiple tasks via Anthropic Batch API (50% cost savings).

    Example:
        >>> workflow = BatchProcessingWorkflow()
        >>> requests = [
        ...     BatchRequest(
        ...         task_id="task_1",
        ...         task_type="analyze_logs",
        ...         input_data={"logs": "ERROR: Connection failed..."}
        ...     ),
        ...     BatchRequest(
        ...         task_id="task_2",
        ...         task_type="generate_report",
        ...         input_data={"data": {...}}
        ...     )
        ... ]
        >>> results = await workflow.execute_batch(requests)
        >>> print(f"{sum(r.success for r in results)}/{len(results)} successful")
    """

    def __init__(self, api_key: str | None = None):
        """Initialize batch workflow.

        Args:
            api_key: Anthropic API key (optional, uses ANTHROPIC_API_KEY env var)
        """
        self.batch_provider = AnthropicBatchProvider(api_key=api_key)

    async def execute_batch(
        self,
        requests: list[BatchRequest],
        poll_interval: int = 300,  # 5 minutes
        timeout: int = 86400,  # 24 hours
    ) -> list[BatchResult]:
        """Execute batch of requests.

        Args:
            requests: List of batch requests
            poll_interval: Seconds between status checks (default: 300)
            timeout: Maximum wait time in seconds (default: 86400)

        Returns:
            List of results matching input order

        Raises:
            ValueError: If requests is empty
            TimeoutError: If batch doesn't complete within timeout
            RuntimeError: If batch processing fails

        Example:
            >>> workflow = BatchProcessingWorkflow()
            >>> requests = [
            ...     BatchRequest(
            ...         task_id="task_1",
            ...         task_type="analyze_logs",
            ...         input_data={"logs": "..."}
            ...     )
            ... ]
            >>> results = await workflow.execute_batch(requests)
            >>> for result in results:
            ...     if result.success:
            ...         print(f"Task {result.task_id}: Success")
            ...     else:
            ...         print(f"Task {result.task_id}: {result.error}")
        """
        if not requests:
            raise ValueError("requests cannot be empty")

        # Convert to Anthropic batch format
        api_requests = []
        for req in requests:
            model = get_model("anthropic", req.model_tier)
            if model is None:
                raise ValueError(f"Unknown model tier: {req.model_tier}")

            api_requests.append(
                {
                    "custom_id": req.task_id,
                    "model": model.id,
                    "messages": self._format_messages(req),
                    "max_tokens": 4096,
                }
            )

        # Submit batch
        logger.info(f"Submitting batch of {len(requests)} requests")
        batch_id = self.batch_provider.create_batch(api_requests)

        logger.info(
            f"Batch {batch_id} created, polling every {poll_interval}s "
            f"(max {timeout}s)"
        )

        # Wait for completion
        try:
            raw_results = await self.batch_provider.wait_for_batch(
                batch_id, poll_interval=poll_interval, timeout=timeout
            )
        except TimeoutError:
            logger.error(f"Batch {batch_id} timed out after {timeout}s")
            return [
                BatchResult(
                    task_id=req.task_id,
                    success=False,
                    error="Batch processing timed out",
                )
                for req in requests
            ]
        except RuntimeError as e:
            logger.error(f"Batch {batch_id} failed: {e}")
            return [
                BatchResult(
                    task_id=req.task_id, success=False, error=f"Batch failed: {e}"
                )
                for req in requests
            ]

        # Parse results
        results = []
        for raw in raw_results:
            task_id = raw.get("custom_id", "unknown")

            if "error" in raw:
                error_msg = raw["error"].get("message", "Unknown error")
                results.append(
                    BatchResult(task_id=task_id, success=False, error=error_msg)
                )
            else:
                results.append(
                    BatchResult(
                        task_id=task_id, success=True, output=raw.get("response")
                    )
                )

        # Log summary
        success_count = sum(r.success for r in results)
        logger.info(
            f"Batch {batch_id} completed: {success_count}/{len(results)} successful"
        )

        return results

    def _format_messages(self, request: BatchRequest) -> list[dict[str, str]]:
        """Format request into Anthropic messages format.

        Args:
            request: BatchRequest with task_type and input_data

        Returns:
            List of message dicts for Anthropic API
        """
        # Task-specific prompts
        task_prompts = {
            "analyze_logs": "Analyze the following logs and identify issues:\n\n{logs}",
            "generate_report": "Generate a report based on:\n\n{data}",
            "classify_bulk": "Classify the following items:\n\n{items}",
            "generate_docs": "Generate documentation for:\n\n{code}",
            "generate_tests": "Generate unit tests for:\n\n{code}",
            # Add more task types as needed
        }

        # Get prompt template or use default
        prompt_template = task_prompts.get(
            request.task_type, "Process the following:\n\n{input}"
        )

        # Format with input data
        try:
            content = prompt_template.format(**request.input_data)
        except KeyError as e:
            logger.warning(
                f"Missing required field {e} for task {request.task_type}, "
                f"using raw input"
            )
            content = prompt_template.format(input=json.dumps(request.input_data))

        return [{"role": "user", "content": content}]

    @classmethod
    def from_json_file(cls, file_path: str) -> "BatchProcessingWorkflow":
        """Create workflow from JSON input file.

        Args:
            file_path: Path to JSON file with batch requests

        Returns:
            BatchProcessingWorkflow instance

        Input file format:
            [
                {
                    "task_id": "1",
                    "task_type": "analyze_logs",
                    "input_data": {"logs": "ERROR: ..."},
                    "model_tier": "capable"
                },
                ...
            ]
        """
        return cls()

    def load_requests_from_file(self, file_path: str) -> list[BatchRequest]:
        """Load batch requests from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            List of BatchRequest objects

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
            ValueError: If file format is invalid
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path) as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Input file must contain a JSON array")

        requests = []
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Each item must be a JSON object")

            requests.append(
                BatchRequest(
                    task_id=item["task_id"],
                    task_type=item["task_type"],
                    input_data=item["input_data"],
                    model_tier=item.get("model_tier", "capable"),
                )
            )

        return requests

    def save_results_to_file(
        self, results: list[BatchResult], output_path: str
    ) -> None:
        """Save batch results to JSON file.

        Args:
            results: List of BatchResult objects
            output_path: Path to output file

        Raises:
            OSError: If file cannot be written
        """
        output_data = [
            {
                "task_id": r.task_id,
                "success": r.success,
                "output": r.output,
                "error": r.error,
            }
            for r in results
        ]

        path = Path(output_path)
        validated_path = _validate_file_path(str(path))
        with open(validated_path, "w") as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Results saved to {validated_path}")
