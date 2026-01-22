"""Document Generation Workflow

A cost-optimized, enterprise-safe documentation pipeline:
1. Haiku: Generate outline from code/specs (cheap, fast)
2. Sonnet: Write each section (capable, chunked for large projects)
3. Opus: Final review + consistency polish (premium, chunked if needed)

Enterprise Features:
- Auto-scaling tokens based on project complexity
- Chunked polish for large documents
- Cost guardrails with configurable max_cost
- Graceful degradation with partial results on errors

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from empathy_os.config import _validate_file_path

from .base import BaseWorkflow, ModelTier
from .step_config import WorkflowStepConfig

logger = logging.getLogger(__name__)

# Approximate cost per 1K tokens (USD) - used for cost estimation
# These are estimates and should be updated as pricing changes
TOKEN_COSTS = {
    ModelTier.CHEAP: {"input": 0.00025, "output": 0.00125},  # Haiku
    ModelTier.CAPABLE: {"input": 0.003, "output": 0.015},  # Sonnet
    ModelTier.PREMIUM: {"input": 0.015, "output": 0.075},  # Opus
}

# Define step configurations for executor-based execution
# Note: max_tokens for polish is dynamically set based on input size
DOC_GEN_STEPS = {
    "polish": WorkflowStepConfig(
        name="polish",
        task_type="final_review",  # Premium tier task
        tier_hint="premium",
        description="Polish and improve documentation for consistency and quality",
        max_tokens=20000,  # Increased to handle large chunked documents
    ),
}


class DocumentGenerationWorkflow(BaseWorkflow):
    """Multi-tier document generation workflow.

    Uses cheap models for outlining, capable models for content
    generation, and premium models for final polish and consistency
    review.

    Usage:
        workflow = DocumentGenerationWorkflow()
        result = await workflow.execute(
            source_code="...",
            doc_type="api_reference",
            audience="developers"
        )
    """

    name = "doc-gen"
    description = "Cost-optimized documentation generation pipeline"
    stages = ["outline", "write", "polish"]
    tier_map = {
        "outline": ModelTier.CHEAP,
        "write": ModelTier.CAPABLE,
        "polish": ModelTier.PREMIUM,
    }

    def __init__(
        self,
        skip_polish_threshold: int = 1000,
        max_sections: int = 10,
        max_write_tokens: int | None = None,  # Auto-scaled if None
        section_focus: list[str] | None = None,
        chunked_generation: bool = True,
        sections_per_chunk: int = 3,
        max_cost: float = 5.0,  # Cost guardrail in USD
        cost_warning_threshold: float = 0.8,  # Warn at 80% of max_cost
        graceful_degradation: bool = True,  # Return partial results on error
        export_path: str | Path | None = None,  # Export docs to file (e.g., "docs/generated")
        max_display_chars: int = 45000,  # Max chars before chunking output
        **kwargs: Any,
    ):
        """Initialize workflow with enterprise-safe defaults.

        Args:
            skip_polish_threshold: Skip premium polish for docs under this
                token count (they're already good enough).
            max_sections: Maximum number of sections to generate.
            max_write_tokens: Maximum tokens for content generation.
                If None, auto-scales based on section count (recommended).
            section_focus: Optional list of specific sections to generate
                (e.g., ["Testing Guide", "API Reference"]).
            chunked_generation: If True, generates large docs in chunks to avoid
                truncation (default True).
            sections_per_chunk: Number of sections to generate per chunk (default 3).
            max_cost: Maximum cost in USD before stopping (default $5).
                Set to 0 to disable cost limits.
            cost_warning_threshold: Percentage of max_cost to trigger warning (default 0.8).
            graceful_degradation: If True, return partial results on errors
                instead of failing completely (default True).
            export_path: Optional directory to export generated docs (e.g., "docs/generated").
                If provided, documentation will be saved to a file automatically.
            max_display_chars: Maximum characters before splitting output into chunks
                for display (default 45000). Helps avoid terminal/UI truncation.

        """
        super().__init__(**kwargs)
        self.skip_polish_threshold = skip_polish_threshold
        self.max_sections = max_sections
        self._user_max_write_tokens = max_write_tokens  # Store user preference
        self.max_write_tokens = max_write_tokens or 16000  # Will be auto-scaled
        self.section_focus = section_focus
        self.chunked_generation = chunked_generation
        self.sections_per_chunk = sections_per_chunk
        self.max_cost = max_cost
        self.cost_warning_threshold = cost_warning_threshold
        self.graceful_degradation = graceful_degradation
        self.export_path = Path(export_path) if export_path else None
        self.max_display_chars = max_display_chars
        self._total_content_tokens: int = 0
        self._accumulated_cost: float = 0.0
        self._cost_warning_issued: bool = False
        self._partial_results: dict = {}

    def _estimate_cost(self, tier: ModelTier, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a given tier and token counts."""
        costs = TOKEN_COSTS.get(tier, TOKEN_COSTS[ModelTier.CAPABLE])
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        return input_cost + output_cost

    def _track_cost(
        self,
        tier: ModelTier,
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[float, bool]:
        """Track accumulated cost and check against limits.

        Returns:
            Tuple of (cost_for_this_call, should_stop)

        """
        cost = self._estimate_cost(tier, input_tokens, output_tokens)
        self._accumulated_cost += cost

        # Check warning threshold
        if (
            self.max_cost > 0
            and not self._cost_warning_issued
            and self._accumulated_cost >= self.max_cost * self.cost_warning_threshold
        ):
            self._cost_warning_issued = True
            logger.warning(
                f"Doc-gen cost approaching limit: ${self._accumulated_cost:.2f} "
                f"of ${self.max_cost:.2f} ({self.cost_warning_threshold * 100:.0f}% threshold)",
            )

        # Check if we should stop
        should_stop = self.max_cost > 0 and self._accumulated_cost >= self.max_cost
        if should_stop:
            logger.warning(
                f"Doc-gen cost limit reached: ${self._accumulated_cost:.2f} >= ${self.max_cost:.2f}",
            )

        return cost, should_stop

    def _auto_scale_tokens(self, section_count: int) -> int:
        """Auto-scale max_write_tokens based on section count.

        Enterprise projects may have 20+ sections requiring more tokens.
        """
        if self._user_max_write_tokens is not None:
            return self._user_max_write_tokens  # User override

        # Base: 2000 tokens per section, minimum 16000, maximum 64000
        scaled = max(16000, min(64000, section_count * 2000))
        logger.info(f"Auto-scaled max_write_tokens to {scaled} for {section_count} sections")
        return scaled

    def _export_document(
        self,
        document: str,
        doc_type: str,
        report: str | None = None,
    ) -> tuple[Path | None, Path | None]:
        """Export generated documentation to file.

        Args:
            document: The generated documentation content
            doc_type: Document type for naming
            report: Optional report to save alongside document

        Returns:
            Tuple of (doc_path, report_path) or (None, None) if export disabled

        """
        if not self.export_path:
            return None, None

        # Create export directory
        self.export_path.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_doc_type = doc_type.replace(" ", "_").replace("/", "-").lower()
        doc_filename = f"{safe_doc_type}_{timestamp}.md"
        report_filename = f"{safe_doc_type}_{timestamp}_report.txt"

        doc_path = self.export_path / doc_filename
        report_path = self.export_path / report_filename if report else None

        # Write document
        try:
            validated_doc_path = _validate_file_path(str(doc_path))
            validated_doc_path.write_text(document, encoding="utf-8")
            logger.info(f"Documentation exported to: {validated_doc_path}")

            # Write report if provided
            if report and report_path:
                validated_report_path = _validate_file_path(str(report_path))
                validated_report_path.write_text(report, encoding="utf-8")
                logger.info(f"Report exported to: {validated_report_path}")

            return validated_doc_path, validated_report_path if report else None
        except (OSError, ValueError) as e:
            logger.error(f"Failed to export documentation: {e}")
            return None, None

    def _chunk_output_for_display(self, content: str, chunk_prefix: str = "PART") -> list[str]:
        """Split large output into displayable chunks.

        Args:
            content: The content to chunk
            chunk_prefix: Prefix for chunk headers

        Returns:
            List of content chunks, each under max_display_chars

        """
        if len(content) <= self.max_display_chars:
            return [content]

        chunks = []
        # Try to split on section boundaries (## headers)
        import re

        sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)

        current_chunk = ""
        chunk_num = 1

        for section in sections:
            # If adding this section would exceed limit, save current chunk
            if current_chunk and len(current_chunk) + len(section) > self.max_display_chars:
                chunks.append(
                    f"{'=' * 60}\n{chunk_prefix} {chunk_num} of {{total}}\n{'=' * 60}\n\n"
                    + current_chunk,
                )
                chunk_num += 1
                current_chunk = section
            else:
                current_chunk += section

        # Add final chunk
        if current_chunk:
            chunks.append(
                f"{'=' * 60}\n{chunk_prefix} {chunk_num} of {{total}}\n{'=' * 60}\n\n"
                + current_chunk,
            )

        # Update total count in all chunks
        total = len(chunks)
        chunks = [chunk.format(total=total) for chunk in chunks]

        return chunks

    def should_skip_stage(self, stage_name: str, input_data: Any) -> tuple[bool, str | None]:
        """Skip polish for short documents."""
        if stage_name == "polish":
            if self._total_content_tokens < self.skip_polish_threshold:
                self.tier_map["polish"] = ModelTier.CAPABLE
                return False, None
        return False, None

    async def run_stage(
        self,
        stage_name: str,
        tier: ModelTier,
        input_data: Any,
    ) -> tuple[Any, int, int]:
        """Execute a document generation stage."""
        if stage_name == "outline":
            return await self._outline(input_data, tier)
        if stage_name == "write":
            return await self._write(input_data, tier)
        if stage_name == "polish":
            return await self._polish(input_data, tier)
        raise ValueError(f"Unknown stage: {stage_name}")

    async def _outline(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Generate document outline from source."""
        source_code = input_data.get("source_code", "")
        target = input_data.get("target", "")
        doc_type = input_data.get("doc_type", "general")
        audience = input_data.get("audience", "developers")

        # Use target if source_code not provided
        content_to_document = source_code or target

        # If target looks like a file path and source_code wasn't provided, read the file
        if not source_code and target:
            from pathlib import Path

            target_path = Path(target)
            if target_path.exists() and target_path.is_file():
                try:
                    content_to_document = target_path.read_text(encoding="utf-8")
                    # Prepend file info for context
                    content_to_document = f"# File: {target}\n\n{content_to_document}"
                except Exception as e:
                    # If we can't read the file, log and use the path as-is
                    import logging

                    logging.getLogger(__name__).warning(f"Could not read file {target}: {e}")
            elif target_path.suffix in (
                ".py",
                ".js",
                ".ts",
                ".tsx",
                ".java",
                ".go",
                ".rs",
                ".md",
                ".txt",
            ):
                # Looks like a file path but doesn't exist - warn
                import logging

                logging.getLogger(__name__).warning(
                    f"Target appears to be a file path but doesn't exist: {target}",
                )

        system = """You are a technical writer. Create a detailed outline for documentation.

Based on the content provided, generate an outline with:
1. Logical section structure (5-8 sections)
2. Brief description of each section's purpose
3. Key points to cover in each section

Format as a numbered list with section titles and descriptions."""

        user_message = f"""Create a documentation outline:

Document Type: {doc_type}
Target Audience: {audience}

Content to document:
{content_to_document[:4000]}"""

        response, input_tokens, output_tokens = await self._call_llm(
            tier,
            system,
            user_message,
            max_tokens=1000,
        )

        return (
            {
                "outline": response,
                "doc_type": doc_type,
                "audience": audience,
                "content_to_document": content_to_document,
            },
            input_tokens,
            output_tokens,
        )

    def _parse_outline_sections(self, outline: str) -> list[str]:
        """Parse top-level section titles from the outline.

        Only matches main sections like "1. Introduction", "2. Setup", etc.
        Ignores sub-sections like "2.1 Prerequisites" or nested items.
        """
        import re

        sections = []
        # Match only top-level sections: digit followed by period and space/letter
        # e.g., "1. Introduction" but NOT "1.1 Sub-section" or "2.1.3 Deep"
        top_level_pattern = re.compile(r"^(\d+)\.\s+([A-Za-z].*)")

        for line in outline.split("\n"):
            stripped = line.strip()
            match = top_level_pattern.match(stripped)
            if match:
                # section_num = match.group(1) - not needed, only extracting title
                title = match.group(2).strip()
                # Remove any trailing description after " - "
                if " - " in title:
                    title = title.split(" - ")[0].strip()
                sections.append(title)

        return sections

    async def _write(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Write content based on the outline."""
        outline = input_data.get("outline", "")
        doc_type = input_data.get("doc_type", "general")
        audience = input_data.get("audience", "developers")
        content_to_document = input_data.get("content_to_document", "")

        # Parse sections from outline
        sections = self._parse_outline_sections(outline)

        # Auto-scale tokens based on section count
        self.max_write_tokens = self._auto_scale_tokens(len(sections))

        # Use chunked generation for large outlines (more than sections_per_chunk * 2)
        use_chunking = (
            self.chunked_generation
            and len(sections) > self.sections_per_chunk * 2
            and not self.section_focus  # Don't chunk if already focused
        )

        if use_chunking:
            return await self._write_chunked(
                sections,
                outline,
                doc_type,
                audience,
                content_to_document,
                tier,
            )

        # Handle section_focus for targeted generation
        section_instruction = ""
        if self.section_focus:
            sections_list = ", ".join(self.section_focus)
            section_instruction = f"""
IMPORTANT: Focus ONLY on generating these specific sections:
{sections_list}

Generate comprehensive, detailed content for each of these sections."""

        system = f"""You are a technical writer. Write comprehensive documentation.

Based on the outline provided, write full content for each section:
1. Use clear, professional language
2. Include code examples where appropriate
3. Use markdown formatting
4. Be thorough and detailed - do NOT truncate sections
5. Target the specified audience
6. Complete ALL sections before stopping
{section_instruction}

Write the complete document with all sections."""

        user_message = f"""Write documentation based on this outline:

Document Type: {doc_type}
Target Audience: {audience}

Outline:
{outline}

Source content for reference:
{content_to_document[:5000]}"""

        response, input_tokens, output_tokens = await self._call_llm(
            tier,
            system,
            user_message,
            max_tokens=self.max_write_tokens,
        )

        self._total_content_tokens = output_tokens

        return (
            {
                "draft_document": response,
                "doc_type": doc_type,
                "audience": audience,
                "outline": outline,
                "chunked": False,
            },
            input_tokens,
            output_tokens,
        )

    async def _write_chunked(
        self,
        sections: list[str],
        outline: str,
        doc_type: str,
        audience: str,
        content_to_document: str,
        tier: ModelTier,
    ) -> tuple[dict, int, int]:
        """Generate documentation in chunks to avoid truncation.

        Enterprise-safe: includes cost tracking and graceful degradation.
        """
        all_content: list[str] = []
        total_input_tokens: int = 0
        total_output_tokens: int = 0
        stopped_early: bool = False
        error_message: str | None = None

        # Split sections into chunks
        chunks = []
        for i in range(0, len(sections), self.sections_per_chunk):
            chunks.append(sections[i : i + self.sections_per_chunk])

        logger.info(f"Generating documentation in {len(chunks)} chunks")

        for chunk_idx, chunk_sections in enumerate(chunks):
            sections_list = ", ".join(chunk_sections)

            # Build context about what came before
            previous_context = ""
            if chunk_idx > 0 and all_content:
                # Include last 500 chars of previous content for continuity
                previous_context = f"""
Previous sections already written (for context/continuity):
...{all_content[-1][-500:]}

Continue with the next sections, maintaining consistent style and terminology."""

            system = f"""You are a technical writer. Write comprehensive documentation.

Write ONLY the following sections (you are generating part {chunk_idx + 1} of {len(chunks)}):
{sections_list}

Requirements:
1. Use clear, professional language
2. Include code examples where appropriate
3. Use markdown formatting with ## headers
4. Be thorough and detailed - complete each section fully
5. Target {audience} audience
6. Write ONLY these specific sections, nothing else"""

            user_message = f"""Write documentation for these specific sections:

Document Type: {doc_type}
Target Audience: {audience}

Sections to write: {sections_list}

Full outline (for context):
{outline}

Source content for reference:
{content_to_document[:3000]}
{previous_context}"""

            try:
                response, input_tokens, output_tokens = await self._call_llm(
                    tier,
                    system,
                    user_message,
                    max_tokens=self.max_write_tokens // len(chunks) + 2000,
                )

                # Track cost and check limits
                _, should_stop = self._track_cost(tier, input_tokens, output_tokens)

                all_content.append(response)
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens

                logger.info(
                    f"Chunk {chunk_idx + 1}/{len(chunks)} complete: "
                    f"{len(response)} chars, {output_tokens} tokens, "
                    f"cost so far: ${self._accumulated_cost:.2f}",
                )

                # Check cost limit
                if should_stop:
                    stopped_early = True
                    remaining = len(chunks) - chunk_idx - 1
                    error_message = (
                        f"Cost limit reached (${self._accumulated_cost:.2f}). "
                        f"Stopped after {chunk_idx + 1}/{len(chunks)} chunks. "
                        f"{remaining} chunks not generated."
                    )
                    logger.warning(error_message)
                    break

            except Exception as e:
                error_message = f"Error generating chunk {chunk_idx + 1}: {e}"
                logger.error(error_message)
                if not self.graceful_degradation:
                    raise
                stopped_early = True
                break

        # Combine all chunks
        combined_document = "\n\n".join(all_content)
        self._total_content_tokens = total_output_tokens

        # Store partial results for graceful degradation
        self._partial_results = {
            "draft_document": combined_document,
            "sections_completed": len(all_content),
            "sections_total": len(chunks),
        }

        result = {
            "draft_document": combined_document,
            "doc_type": doc_type,
            "audience": audience,
            "outline": outline,
            "chunked": True,
            "chunk_count": len(chunks),
            "chunks_completed": len(all_content),
            "stopped_early": stopped_early,
            "accumulated_cost": self._accumulated_cost,
        }

        if error_message:
            result["warning"] = error_message

        return (result, total_input_tokens, total_output_tokens)

    async def _polish(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Final review and consistency polish using LLM.

        Enterprise-safe: chunks large documents to avoid truncation.
        Supports XML-enhanced prompts when enabled in workflow config.
        """
        draft_document = input_data.get("draft_document", "")
        doc_type = input_data.get("doc_type", "general")
        audience = input_data.get("audience", "developers")

        # Check if document is too large and needs chunked polishing
        # Rough estimate: 4 chars per token, 10k tokens threshold for chunking
        estimated_tokens = len(draft_document) // 4
        needs_chunked_polish = estimated_tokens > 10000

        if needs_chunked_polish:
            logger.info(
                f"Large document detected (~{estimated_tokens} tokens). "
                "Using chunked polish for enterprise safety.",
            )
            return await self._polish_chunked(input_data, tier)

        # Build input payload for prompt
        input_payload = f"""Document Type: {doc_type}
Target Audience: {audience}

Draft:
{draft_document}"""

        # Check if XML prompts are enabled
        if self._is_xml_enabled():
            # Use XML-enhanced prompt
            user_message = self._render_xml_prompt(
                role="senior technical editor",
                goal="Polish and improve the documentation for consistency and quality",
                instructions=[
                    "Standardize terminology and formatting",
                    "Improve clarity and flow",
                    "Add missing cross-references",
                    "Fix grammatical issues",
                    "Identify gaps and add helpful notes",
                    "Ensure examples are complete and accurate",
                ],
                constraints=[
                    "Maintain the original structure and intent",
                    "Keep content appropriate for the target audience",
                    "Preserve code examples while improving explanations",
                ],
                input_type="documentation_draft",
                input_payload=input_payload,
                extra={
                    "doc_type": doc_type,
                    "audience": audience,
                },
            )
            system = None  # XML prompt includes all context
        else:
            # Use legacy plain text prompts
            system = """You are a senior technical editor. Polish and improve the documentation:

1. CONSISTENCY:
   - Standardize terminology
   - Fix formatting inconsistencies
   - Ensure consistent code style

2. QUALITY:
   - Improve clarity and flow
   - Add missing cross-references
   - Fix grammatical issues

3. COMPLETENESS:
   - Identify gaps
   - Add helpful notes or warnings
   - Ensure examples are complete

Return the polished document with improvements noted at the end."""

            user_message = f"""Polish this documentation:

{input_payload}"""

        # Calculate polish tokens based on draft size (at least as much as write stage)
        polish_max_tokens = max(self.max_write_tokens, 20000)

        # Try executor-based execution first (Phase 3 pattern)
        if self._executor is not None or self._api_key:
            try:
                step = DOC_GEN_STEPS["polish"]
                # Override step max_tokens with dynamic value
                step.max_tokens = polish_max_tokens
                response, input_tokens, output_tokens, cost = await self.run_step_with_executor(
                    step=step,
                    prompt=user_message,
                    system=system,
                )
            except Exception:
                # Fall back to legacy _call_llm if executor fails
                response, input_tokens, output_tokens = await self._call_llm(
                    tier,
                    system or "",
                    user_message,
                    max_tokens=polish_max_tokens,
                )
        else:
            # Legacy path for backward compatibility
            response, input_tokens, output_tokens = await self._call_llm(
                tier,
                system or "",
                user_message,
                max_tokens=polish_max_tokens,
            )

        # Parse XML response if enforcement is enabled
        parsed_data = self._parse_xml_response(response)

        result = {
            "document": response,
            "doc_type": doc_type,
            "audience": audience,
            "model_tier_used": tier.value,
        }

        # Merge parsed XML data if available
        if parsed_data.get("xml_parsed"):
            result.update(
                {
                    "xml_parsed": True,
                    "summary": parsed_data.get("summary"),
                    "findings": parsed_data.get("findings", []),
                    "checklist": parsed_data.get("checklist", []),
                },
            )

        # Add formatted report for human readability
        result["formatted_report"] = format_doc_gen_report(result, input_data)

        # Export documentation if export_path is configured
        doc_path, report_path = self._export_document(
            document=response,
            doc_type=doc_type,
            report=result["formatted_report"],
        )
        if doc_path:
            result["export_path"] = str(doc_path)
            result["report_path"] = str(report_path) if report_path else None
            logger.info(f"Documentation saved to: {doc_path}")

        # Chunk output for display if needed
        output_chunks = self._chunk_output_for_display(
            result["formatted_report"],
            chunk_prefix="DOC OUTPUT",
        )
        if len(output_chunks) > 1:
            result["output_chunks"] = output_chunks
            result["output_chunk_count"] = len(output_chunks)
            logger.info(
                f"Report split into {len(output_chunks)} chunks for display "
                f"(total {len(result['formatted_report'])} chars)",
            )

        return (result, input_tokens, output_tokens)

    async def _polish_chunked(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Polish large documents in chunks to avoid truncation.

        Splits the document by section headers and polishes each chunk separately,
        then combines the results.
        """
        import re

        draft_document = input_data.get("draft_document", "")
        doc_type = input_data.get("doc_type", "general")
        audience = input_data.get("audience", "developers")

        # Split document by major section headers (## headers)
        sections = re.split(r"(?=^## )", draft_document, flags=re.MULTILINE)
        sections = [s.strip() for s in sections if s.strip()]

        if len(sections) <= 1:
            # If we can't split by sections, split by character count
            chunk_size = 15000  # ~3750 tokens per chunk
            sections = [
                draft_document[i : i + chunk_size]
                for i in range(0, len(draft_document), chunk_size)
            ]

        logger.info(f"Polishing document in {len(sections)} chunks")

        polished_chunks: list[str] = []
        total_input_tokens: int = 0
        total_output_tokens: int = 0

        for chunk_idx, section in enumerate(sections):
            system = """You are a senior technical editor. Polish this section of documentation:

1. Standardize terminology and formatting
2. Improve clarity and flow
3. Fix grammatical issues
4. Ensure code examples are complete and accurate

Return ONLY the polished section. Do not add commentary."""

            user_message = f"""Polish this documentation section (part {chunk_idx + 1} of {len(sections)}):

Document Type: {doc_type}
Target Audience: {audience}

Section to polish:
{section}"""

            try:
                response, input_tokens, output_tokens = await self._call_llm(
                    tier,
                    system,
                    user_message,
                    max_tokens=8000,
                )

                # Track cost
                _, should_stop = self._track_cost(tier, input_tokens, output_tokens)

                polished_chunks.append(response)
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens

                logger.info(
                    f"Polish chunk {chunk_idx + 1}/{len(sections)} complete, "
                    f"cost so far: ${self._accumulated_cost:.2f}",
                )

                if should_stop:
                    logger.warning(
                        f"Cost limit reached during polish. "
                        f"Returning {len(polished_chunks)}/{len(sections)} polished chunks.",
                    )
                    # Add remaining sections unpolished
                    polished_chunks.extend(sections[chunk_idx + 1 :])
                    break

            except Exception as e:
                logger.error(f"Error polishing chunk {chunk_idx + 1}: {e}")
                if self.graceful_degradation:
                    # Keep original section on error
                    polished_chunks.append(section)
                else:
                    raise

        # Combine polished chunks
        polished_document = "\n\n".join(polished_chunks)

        result = {
            "document": polished_document,
            "doc_type": doc_type,
            "audience": audience,
            "model_tier_used": tier.value,
            "polish_chunked": True,
            "polish_chunks": len(sections),
            "accumulated_cost": self._accumulated_cost,
        }

        # Add formatted report
        result["formatted_report"] = format_doc_gen_report(result, input_data)

        # Export documentation if export_path is configured
        doc_path, report_path = self._export_document(
            document=polished_document,
            doc_type=doc_type,
            report=result["formatted_report"],
        )
        if doc_path:
            result["export_path"] = str(doc_path)
            result["report_path"] = str(report_path) if report_path else None
            logger.info(f"Documentation saved to: {doc_path}")

        # Chunk output for display if needed
        output_chunks = self._chunk_output_for_display(
            result["formatted_report"],
            chunk_prefix="DOC OUTPUT",
        )
        if len(output_chunks) > 1:
            result["output_chunks"] = output_chunks
            result["output_chunk_count"] = len(output_chunks)
            logger.info(
                f"Report split into {len(output_chunks)} chunks for display "
                f"(total {len(result['formatted_report'])} chars)",
            )

        return (result, total_input_tokens, total_output_tokens)


def format_doc_gen_report(result: dict, input_data: dict) -> str:
    """Format document generation output as a human-readable report.

    Args:
        result: The polish stage result
        input_data: Input data from previous stages

    Returns:
        Formatted report string

    """
    lines = []

    # Header
    doc_type = result.get("doc_type", "general").replace("_", " ").title()
    audience = result.get("audience", "developers").title()

    lines.append("=" * 60)
    lines.append("DOCUMENTATION GENERATION REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Document Type: {doc_type}")
    lines.append(f"Target Audience: {audience}")
    lines.append("")

    # Outline summary
    outline = input_data.get("outline", "")
    if outline:
        lines.append("-" * 60)
        lines.append("DOCUMENT OUTLINE")
        lines.append("-" * 60)
        # Show just a preview of the outline
        outline_lines = outline.split("\n")[:10]
        lines.extend(outline_lines)
        if len(outline.split("\n")) > 10:
            lines.append("...")
        lines.append("")

    # Generated document
    document = result.get("document", "")
    if document:
        lines.append("-" * 60)
        lines.append("GENERATED DOCUMENTATION")
        lines.append("-" * 60)
        lines.append("")
        lines.append(document)
        lines.append("")

    # Statistics
    word_count = len(document.split()) if document else 0
    section_count = document.count("##") if document else 0  # Count markdown headers
    was_chunked = input_data.get("chunked", False)
    chunk_count = input_data.get("chunk_count", 0)
    chunks_completed = input_data.get("chunks_completed", chunk_count)
    stopped_early = input_data.get("stopped_early", False)
    accumulated_cost = result.get("accumulated_cost", 0)
    polish_chunked = result.get("polish_chunked", False)

    lines.append("-" * 60)
    lines.append("STATISTICS")
    lines.append("-" * 60)
    lines.append(f"Word Count: {word_count}")
    lines.append(f"Section Count: ~{section_count}")
    if was_chunked:
        if stopped_early:
            lines.append(
                f"Generation Mode: Chunked ({chunks_completed}/{chunk_count} chunks completed)",
            )
        else:
            lines.append(f"Generation Mode: Chunked ({chunk_count} chunks)")
    if polish_chunked:
        polish_chunks = result.get("polish_chunks", 0)
        lines.append(f"Polish Mode: Chunked ({polish_chunks} sections)")
    if accumulated_cost > 0:
        lines.append(f"Estimated Cost: ${accumulated_cost:.2f}")
    lines.append("")

    # Export info
    export_path = result.get("export_path")
    if export_path:
        lines.append("-" * 60)
        lines.append("FILE EXPORT")
        lines.append("-" * 60)
        lines.append(f"Documentation saved to: {export_path}")
        report_path = result.get("report_path")
        if report_path:
            lines.append(f"Report saved to: {report_path}")
        lines.append("")
        lines.append("Full documentation is available in the exported file.")
        lines.append("")

    # Warning notice (cost limit, errors, etc.)
    warning = input_data.get("warning") or result.get("warning")
    if warning or stopped_early:
        lines.append("-" * 60)
        lines.append("⚠️  WARNING")
        lines.append("-" * 60)
        if warning:
            lines.append(warning)
        if stopped_early and not warning:
            lines.append("Generation stopped early due to cost or error limits.")
        lines.append("")

    # Truncation detection and scope notice
    truncation_indicators = [
        document.rstrip().endswith("..."),
        document.rstrip().endswith("-"),
        "```" in document and document.count("```") % 2 != 0,  # Unclosed code block
        any(
            phrase in document.lower()
            for phrase in ["continued in", "see next section", "to be continued"]
        ),
    ]

    # Count planned sections from outline (top-level only)
    import re

    planned_sections = 0
    top_level_pattern = re.compile(r"^(\d+)\.\s+([A-Za-z].*)")
    if outline:
        for line in outline.split("\n"):
            stripped = line.strip()
            if top_level_pattern.match(stripped):
                planned_sections += 1

    is_truncated = any(truncation_indicators) or (
        planned_sections > 0 and section_count < planned_sections - 1
    )

    if is_truncated or planned_sections > section_count + 1:
        lines.append("-" * 60)
        lines.append("SCOPE NOTICE")
        lines.append("-" * 60)
        lines.append("⚠️  DOCUMENTATION MAY BE INCOMPLETE")
        if planned_sections > 0:
            lines.append(f"   Planned sections: {planned_sections}")
            lines.append(f"   Generated sections: {section_count}")
        lines.append("")
        lines.append("To generate missing sections, re-run with section_focus:")
        lines.append("   workflow = DocumentGenerationWorkflow(")
        lines.append('       section_focus=["Testing Guide", "API Reference"]')
        lines.append("   )")
        lines.append("")

    # Footer
    lines.append("=" * 60)
    model_tier = result.get("model_tier_used", "unknown")
    lines.append(f"Generated using {model_tier} tier model")
    lines.append("=" * 60)

    return "\n".join(lines)
