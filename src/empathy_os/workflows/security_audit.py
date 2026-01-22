"""Security Audit Workflow

OWASP-focused security scan with intelligent vulnerability assessment.
Integrates with team security decisions to filter known false positives.

Stages:
1. triage (CHEAP) - Quick scan for common vulnerability patterns
2. analyze (CAPABLE) - Deep analysis of flagged areas
3. assess (CAPABLE) - Risk scoring and severity classification
4. remediate (PREMIUM) - Generate remediation plan (conditional)

Copyright 2025 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from .base import BaseWorkflow, ModelTier
from .step_config import WorkflowStepConfig

logger = logging.getLogger(__name__)

# Define step configurations for executor-based execution
SECURITY_STEPS = {
    "remediate": WorkflowStepConfig(
        name="remediate",
        task_type="final_review",  # Premium tier task
        tier_hint="premium",
        description="Generate remediation plan for security vulnerabilities",
        max_tokens=3000,
    ),
}

# Directories to skip during scanning (build artifacts, third-party code)
SKIP_DIRECTORIES = {
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".next",  # Next.js build output
    "dist",
    "build",
    ".tox",
    "site",  # MkDocs output
    "ebook-site",
    "website",  # Website build artifacts
    "anthropic-cookbook",  # Third-party examples
    ".eggs",
    "*.egg-info",
    "htmlcov",  # Coverage report artifacts
    "htmlcov_logging",  # Coverage report artifacts
    ".coverage",  # Coverage data
    "vscode-extension",  # VSCode extension code (separate security review)
    "vscode-memory-panel",  # VSCode panel code
    "wizard-dashboard",  # Dashboard build
}

# Patterns that indicate a line is DETECTION code, not vulnerable code
# These help avoid false positives when scanning security tools
DETECTION_PATTERNS = [
    r'["\']eval\s*\(["\']',  # String literal like "eval(" (detection, not execution)
    r'["\']exec\s*\(["\']',  # String literal like "exec(" (detection, not execution)
    r"in\s+content",  # Pattern detection like "eval(" in content
    r"re\.compile",  # Regex compilation for detection
    r"\.finditer\(",  # Regex matching for detection
    r"\.search\(",  # Regex searching for detection
]

# Known fake/test credential patterns to ignore
FAKE_CREDENTIAL_PATTERNS = [
    r"EXAMPLE",  # AWS example keys
    r"FAKE",
    r"TEST",
    r"your-.*-here",
    r'"your-key"',  # Placeholder key
    r"abc123xyz",
    r"\.\.\.",  # Placeholder with ellipsis
    r"test-key",
    r"mock",
    r'"hardcoded_secret"',  # Literal example text
    r'"secret"$',  # Generic "secret" as value
    r'"secret123"',  # Test password
    r'"password"$',  # Generic password as value
    r"_PATTERN",  # Pattern constants
    r"_EXAMPLE",  # Example constants
]

# Files/paths that contain security examples/tests (not vulnerabilities)
SECURITY_EXAMPLE_PATHS = [
    "owasp_patterns.py",
    "vulnerability_scanner.py",
    "test_security",
    "test_secrets",
    "test_owasp",
    "secrets_detector.py",  # Security tool with pattern definitions
    "pii_scrubber.py",  # Privacy tool
    "secure_memdocs",  # Secure storage module
    "/security/",  # Security modules
    "/benchmarks/",  # Benchmark files with test fixtures
    "benchmark_",  # Benchmark files (e.g., benchmark_caching.py)
    "phase_2_setup.py",  # Setup file with educational patterns
]

# Patterns indicating test fixture data (code written to temp files for testing)
TEST_FIXTURE_PATTERNS = [
    r"SECURITY_TEST_FILES\s*=",  # Dict of test fixture code
    r"write_text\s*\(",  # Writing test data to temp files
    r"# UNSAFE - DO NOT USE",  # Educational comments showing bad patterns
    r"# SAFE -",  # Educational comments showing good patterns
    r"# INJECTION RISK",  # Educational markers
    r"pragma:\s*allowlist\s*secret",  # Explicit allowlist marker
]

# Test file patterns - findings here are informational, not critical
TEST_FILE_PATTERNS = [
    r"/tests/",
    r"/test_",
    r"_test\.py$",
    r"_demo\.py$",
    r"_example\.py$",
    r"/examples/",
    r"/demo",
    r"coach/vscode-extension",  # Example VSCode extension
]

# Common security vulnerability patterns (OWASP Top 10 inspired)
SECURITY_PATTERNS = {
    "sql_injection": {
        "patterns": [
            r'execute\s*\(\s*["\'].*%s',
            r'cursor\.execute\s*\(\s*f["\']',
            r"\.format\s*\(.*\).*execute",
        ],
        "severity": "critical",
        "owasp": "A03:2021 Injection",
    },
    "xss": {
        "patterns": [
            r"innerHTML\s*=",
            r"dangerouslySetInnerHTML",
            r"document\.write\s*\(",
        ],
        "severity": "high",
        "owasp": "A03:2021 Injection",
    },
    "hardcoded_secret": {
        "patterns": [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][A-Za-z0-9]{20,}["\']',
        ],
        "severity": "critical",
        "owasp": "A02:2021 Cryptographic Failures",
    },
    "insecure_random": {
        "patterns": [
            r"random\.\w+\s*\(",
            r"Math\.random\s*\(",
        ],
        "severity": "medium",
        "owasp": "A02:2021 Cryptographic Failures",
    },
    "path_traversal": {
        "patterns": [
            r"open\s*\([^)]*\+[^)]*\)",
            r"readFile\s*\([^)]*\+[^)]*\)",
        ],
        "severity": "high",
        "owasp": "A01:2021 Broken Access Control",
    },
    "command_injection": {
        "patterns": [
            r"subprocess\.\w+\s*\([^)]*shell\s*=\s*True",
            r"os\.system\s*\(",
            r"eval\s*\(",
            r"exec\s*\(",
        ],
        "severity": "critical",
        "owasp": "A03:2021 Injection",
    },
}


class SecurityAuditWorkflow(BaseWorkflow):
    """OWASP-focused security audit with team decision integration.

    Scans code for security vulnerabilities while respecting
    team decisions about false positives and accepted risks.
    """

    name = "security-audit"
    description = "OWASP-focused security scan with vulnerability assessment"
    stages = ["triage", "analyze", "assess", "remediate"]
    tier_map = {
        "triage": ModelTier.CHEAP,
        "analyze": ModelTier.CAPABLE,
        "assess": ModelTier.CAPABLE,
        "remediate": ModelTier.PREMIUM,
    }

    def __init__(
        self,
        patterns_dir: str = "./patterns",
        skip_remediate_if_clean: bool = True,
        use_crew_for_assessment: bool = True,
        use_crew_for_remediation: bool = False,
        crew_config: dict | None = None,
        **kwargs: Any,
    ):
        """Initialize security audit workflow.

        Args:
            patterns_dir: Directory containing security decisions
            skip_remediate_if_clean: Skip remediation if no high/critical findings
            use_crew_for_assessment: Use SecurityAuditCrew for vulnerability assessment (default: True)
            use_crew_for_remediation: Use SecurityAuditCrew for enhanced remediation (default: True)
            crew_config: Configuration dict for SecurityAuditCrew
            **kwargs: Additional arguments passed to BaseWorkflow

        """
        super().__init__(**kwargs)
        self.patterns_dir = patterns_dir
        self.skip_remediate_if_clean = skip_remediate_if_clean
        self.use_crew_for_assessment = use_crew_for_assessment
        self.use_crew_for_remediation = use_crew_for_remediation
        self.crew_config = crew_config or {}
        self._has_critical: bool = False
        self._team_decisions: dict[str, dict] = {}
        self._crew: Any = None
        self._crew_available = False
        self._load_team_decisions()

    def _load_team_decisions(self) -> None:
        """Load team security decisions for false positive filtering."""
        decisions_file = Path(self.patterns_dir) / "security" / "team_decisions.json"
        if decisions_file.exists():
            try:
                with open(decisions_file) as f:
                    data = json.load(f)
                    for decision in data.get("decisions", []):
                        key = decision.get("finding_hash", "")
                        self._team_decisions[key] = decision
            except (json.JSONDecodeError, OSError):
                pass

    async def _initialize_crew(self) -> None:
        """Initialize the SecurityAuditCrew."""
        if self._crew is not None:
            return

        try:
            from empathy_llm_toolkit.agent_factory.crews.security_audit import SecurityAuditCrew

            self._crew = SecurityAuditCrew()
            self._crew_available = True
            logger.info("SecurityAuditCrew initialized successfully")
        except ImportError as e:
            logger.warning(f"SecurityAuditCrew not available: {e}")
            self._crew_available = False

    def should_skip_stage(self, stage_name: str, input_data: Any) -> tuple[bool, str | None]:
        """Skip remediation stage if no critical/high findings.

        Args:
            stage_name: Name of the stage to check
            input_data: Current workflow data

        Returns:
            Tuple of (should_skip, reason)

        """
        if stage_name == "remediate" and self.skip_remediate_if_clean:
            if not self._has_critical:
                return True, "No high/critical findings requiring remediation"
        return False, None

    async def run_stage(
        self,
        stage_name: str,
        tier: ModelTier,
        input_data: Any,
    ) -> tuple[Any, int, int]:
        """Route to specific stage implementation."""
        if stage_name == "triage":
            return await self._triage(input_data, tier)
        if stage_name == "analyze":
            return await self._analyze(input_data, tier)
        if stage_name == "assess":
            return await self._assess(input_data, tier)
        if stage_name == "remediate":
            return await self._remediate(input_data, tier)
        raise ValueError(f"Unknown stage: {stage_name}")

    async def _triage(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Quick scan for common vulnerability patterns.

        Uses regex patterns to identify potential security issues
        across the codebase for further analysis.
        """
        target_path = input_data.get("path", ".")
        file_types = input_data.get("file_types", [".py", ".ts", ".tsx", ".js", ".jsx"])

        findings: list[dict] = []
        files_scanned = 0

        target = Path(target_path)
        if target.exists():
            for ext in file_types:
                for file_path in target.rglob(f"*{ext}"):
                    # Skip excluded directories
                    if any(skip in str(file_path) for skip in SKIP_DIRECTORIES):
                        continue

                    try:
                        content = file_path.read_text(errors="ignore")
                        lines = content.split("\n")
                        files_scanned += 1

                        for vuln_type, vuln_info in SECURITY_PATTERNS.items():
                            for pattern in vuln_info["patterns"]:
                                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                                for match in matches:
                                    # Find line number and get the line content
                                    line_num = content[: match.start()].count("\n") + 1
                                    line_content = (
                                        lines[line_num - 1] if line_num <= len(lines) else ""
                                    )

                                    # Skip if file is a security example/test file
                                    file_name = str(file_path)
                                    if any(exp in file_name for exp in SECURITY_EXAMPLE_PATHS):
                                        continue

                                    # Skip if this looks like detection/scanning code
                                    if self._is_detection_code(line_content, match.group()):
                                        continue

                                    # Skip fake/test credentials
                                    if vuln_type == "hardcoded_secret":
                                        if self._is_fake_credential(match.group()):
                                            continue

                                    # Skip command_injection in documentation strings
                                    if vuln_type == "command_injection":
                                        if self._is_documentation_or_string(
                                            line_content,
                                            match.group(),
                                        ):
                                            continue

                                    # Check if this is a test file - downgrade to informational
                                    is_test_file = any(
                                        re.search(pat, file_name) for pat in TEST_FILE_PATTERNS
                                    )

                                    # Skip test file findings for hardcoded_secret (expected in tests)
                                    if is_test_file and vuln_type == "hardcoded_secret":
                                        continue

                                    findings.append(
                                        {
                                            "type": vuln_type,
                                            "file": str(file_path),
                                            "line": line_num,
                                            "match": match.group()[:100],
                                            "severity": (
                                                "low" if is_test_file else vuln_info["severity"]
                                            ),
                                            "owasp": vuln_info["owasp"],
                                            "is_test": is_test_file,
                                        },
                                    )
                    except OSError:
                        continue

        input_tokens = len(str(input_data)) // 4
        output_tokens = len(str(findings)) // 4

        return (
            {
                "findings": findings,
                "files_scanned": files_scanned,
                "finding_count": len(findings),
                **input_data,
            },
            input_tokens,
            output_tokens,
        )

    async def _analyze(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Deep analysis of flagged areas.

        Filters findings against team decisions and performs
        deeper analysis of genuine security concerns.
        """
        findings = input_data.get("findings", [])
        analyzed: list[dict] = []

        for finding in findings:
            finding_key = finding.get("type", "")

            # Check team decisions
            decision = self._team_decisions.get(finding_key)
            if decision:
                if decision.get("decision") == "false_positive":
                    finding["status"] = "false_positive"
                    finding["decision_reason"] = decision.get("reason", "")
                    finding["decided_by"] = decision.get("decided_by", "")
                elif decision.get("decision") == "accepted":
                    finding["status"] = "accepted_risk"
                    finding["decision_reason"] = decision.get("reason", "")
                elif decision.get("decision") == "deferred":
                    finding["status"] = "deferred"
                    finding["decision_reason"] = decision.get("reason", "")
                else:
                    finding["status"] = "needs_review"
            else:
                finding["status"] = "needs_review"

            # Add context analysis
            if finding["status"] == "needs_review":
                finding["analysis"] = self._analyze_finding(finding)

            analyzed.append(finding)

        # Separate by status
        needs_review = [f for f in analyzed if f["status"] == "needs_review"]
        false_positives = [f for f in analyzed if f["status"] == "false_positive"]
        accepted = [f for f in analyzed if f["status"] == "accepted_risk"]

        input_tokens = len(str(input_data)) // 4
        output_tokens = len(str(analyzed)) // 4

        return (
            {
                "analyzed_findings": analyzed,
                "needs_review": needs_review,
                "false_positives": false_positives,
                "accepted_risks": accepted,
                "review_count": len(needs_review),
                **input_data,
            },
            input_tokens,
            output_tokens,
        )

    def _analyze_finding(self, finding: dict) -> str:
        """Generate analysis context for a finding."""
        vuln_type = finding.get("type", "")
        analyses = {
            "sql_injection": "Potential SQL injection. Verify parameterized input.",
            "xss": "Potential XSS vulnerability. Check output escaping.",
            "hardcoded_secret": "Hardcoded credential. Use env vars or secrets manager.",
            "insecure_random": "Insecure random. Use secrets module instead.",
            "path_traversal": "Potential path traversal. Validate file paths.",
            "command_injection": "Potential command injection. Avoid shell=True.",
        }
        return analyses.get(vuln_type, "Review for security implications.")

    def _is_detection_code(self, line_content: str, match_text: str) -> bool:
        """Check if a match is actually detection/scanning code, not a vulnerability.

        This prevents false positives when scanning security tools that contain
        patterns like 'if "eval(" in content:' which are detecting vulnerabilities,
        not introducing them.
        """
        # Check if the line contains detection patterns
        for pattern in DETECTION_PATTERNS:
            if re.search(pattern, line_content, re.IGNORECASE):
                return True

        # Check if the match is inside a string literal used for comparison
        # e.g., 'if "eval(" in content:' or 'pattern = r"eval\("'
        if f'"{match_text.strip()}"' in line_content or f"'{match_text.strip()}'" in line_content:
            return True

        return False

    def _is_fake_credential(self, match_text: str) -> bool:
        """Check if a matched credential is obviously fake/for testing.

        This prevents false positives for test fixtures using patterns like
        'AKIAIOSFODNN7EXAMPLE' (AWS official example) or 'test-key-not-real'.
        """
        for pattern in FAKE_CREDENTIAL_PATTERNS:
            if re.search(pattern, match_text, re.IGNORECASE):
                return True
        return False

    def _is_documentation_or_string(self, line_content: str, match_text: str) -> bool:
        """Check if a command injection match is in documentation or string literals.

        This prevents false positives for:
        - Docstrings describing security issues
        - String literals containing example vulnerable code
        - Comments explaining vulnerabilities
        """
        line = line_content.strip()

        # Check if line is a comment
        if line.startswith("#") or line.startswith("//") or line.startswith("*"):
            return True

        # Check if inside a docstring (triple quotes)
        if '"""' in line or "'''" in line:
            return True

        # Check if the match is inside a string literal being defined
        # e.g., 'pattern = r"eval\("' or '"eval(" in content'
        string_patterns = [
            r'["\'].*' + re.escape(match_text.strip()[:10]) + r'.*["\']',  # Inside quotes
            r'r["\'].*' + re.escape(match_text.strip()[:10]),  # Raw string
            r'=\s*["\']',  # String assignment
        ]
        for pattern in string_patterns:
            if re.search(pattern, line):
                return True

        # Check for common documentation patterns
        doc_indicators = [
            "example",
            "vulnerable",
            "insecure",
            "dangerous",
            "pattern",
            "detect",
            "scan",
            "check for",
            "look for",
        ]
        line_lower = line.lower()
        if any(ind in line_lower for ind in doc_indicators):
            return True

        return False

    async def _assess(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Risk scoring and severity classification.

        Calculates overall security risk score and identifies
        critical issues requiring immediate attention.

        When use_crew_for_assessment=True, uses SecurityAuditCrew's
        comprehensive analysis for enhanced vulnerability detection.
        """
        await self._initialize_crew()

        needs_review = input_data.get("needs_review", [])

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for finding in needs_review:
            sev = finding.get("severity", "low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Calculate risk score (0-100)
        risk_score = (
            severity_counts["critical"] * 25
            + severity_counts["high"] * 10
            + severity_counts["medium"] * 3
            + severity_counts["low"] * 1
        )
        risk_score = min(100, risk_score)

        # Set flag for skip logic
        self._has_critical = severity_counts["critical"] > 0 or severity_counts["high"] > 0

        # Group findings by OWASP category
        by_owasp: dict[str, list] = {}
        for finding in needs_review:
            owasp = finding.get("owasp", "Unknown")
            if owasp not in by_owasp:
                by_owasp[owasp] = []
            by_owasp[owasp].append(finding)

        # Use crew for enhanced assessment if available
        crew_enhanced = False
        crew_findings = []
        if self.use_crew_for_assessment and self._crew_available:
            target = input_data.get("path", ".")
            try:
                crew_report = await self._crew.audit(target=target)
                if crew_report and crew_report.findings:
                    crew_enhanced = True
                    # Convert crew findings to workflow format
                    for finding in crew_report.findings:
                        crew_findings.append(
                            {
                                "type": finding.category.value,
                                "title": finding.title,
                                "description": finding.description,
                                "severity": finding.severity.value,
                                "file": finding.file_path or "",
                                "line": finding.line_number or 0,
                                "owasp": finding.category.value,
                                "remediation": finding.remediation or "",
                                "cwe_id": finding.cwe_id or "",
                                "cvss_score": finding.cvss_score or 0.0,
                                "source": "crew",
                            }
                        )
                    # Update severity counts with crew findings
                    for finding in crew_findings:
                        sev = finding.get("severity", "low")
                        severity_counts[sev] = severity_counts.get(sev, 0) + 1
                    # Recalculate risk score with crew findings
                    risk_score = (
                        severity_counts["critical"] * 25
                        + severity_counts["high"] * 10
                        + severity_counts["medium"] * 3
                        + severity_counts["low"] * 1
                    )
                    risk_score = min(100, risk_score)
            except Exception as e:
                logger.warning(f"Crew assessment failed: {e}")

        # Merge crew findings with pattern-based findings
        all_critical = [f for f in needs_review if f.get("severity") == "critical"]
        all_high = [f for f in needs_review if f.get("severity") == "high"]
        if crew_enhanced:
            all_critical.extend([f for f in crew_findings if f.get("severity") == "critical"])
            all_high.extend([f for f in crew_findings if f.get("severity") == "high"])

        assessment = {
            "risk_score": risk_score,
            "risk_level": (
                "critical"
                if risk_score >= 75
                else "high" if risk_score >= 50 else "medium" if risk_score >= 25 else "low"
            ),
            "severity_breakdown": severity_counts,
            "by_owasp_category": {k: len(v) for k, v in by_owasp.items()},
            "critical_findings": all_critical,
            "high_findings": all_high,
            "crew_enhanced": crew_enhanced,
            "crew_findings_count": len(crew_findings) if crew_enhanced else 0,
        }

        input_tokens = len(str(input_data)) // 4
        output_tokens = len(str(assessment)) // 4

        # Build output with assessment
        output = {
            "assessment": assessment,
            **input_data,
        }

        # Add formatted report for human readability
        output["formatted_report"] = format_security_report(output)

        return (
            output,
            input_tokens,
            output_tokens,
        )

    async def _remediate(self, input_data: dict, tier: ModelTier) -> tuple[dict, int, int]:
        """Generate remediation plan for security issues.

        Creates actionable remediation steps prioritized by
        severity and grouped by OWASP category.

        When use_crew_for_remediation=True, uses SecurityAuditCrew's
        Remediation Expert agent for enhanced recommendations.

        Supports XML-enhanced prompts when enabled in workflow config.
        """
        from .security_adapters import _check_crew_available

        assessment = input_data.get("assessment", {})
        critical = assessment.get("critical_findings", [])
        high = assessment.get("high_findings", [])
        target = input_data.get("target", input_data.get("path", ""))

        crew_remediation = None
        crew_enhanced = False

        # Try crew-based remediation first if enabled
        if self.use_crew_for_remediation and _check_crew_available():
            crew_remediation = await self._get_crew_remediation(target, critical + high, assessment)
            if crew_remediation:
                crew_enhanced = True

        # Build findings summary for LLM
        findings_summary = []
        for f in critical:
            findings_summary.append(
                f"CRITICAL: {f.get('type')} in {f.get('file')}:{f.get('line')} - {f.get('owasp')}",
            )
        for f in high:
            findings_summary.append(
                f"HIGH: {f.get('type')} in {f.get('file')}:{f.get('line')} - {f.get('owasp')}",
            )

        # Build input payload for prompt
        input_payload = f"""Target: {target or "codebase"}

Findings:
{chr(10).join(findings_summary) if findings_summary else "No critical or high findings"}

Risk Score: {assessment.get("risk_score", 0)}/100
Risk Level: {assessment.get("risk_level", "unknown")}

Severity Breakdown: {json.dumps(assessment.get("severity_breakdown", {}), indent=2)}"""

        # Check if XML prompts are enabled
        if self._is_xml_enabled():
            # Use XML-enhanced prompt
            user_message = self._render_xml_prompt(
                role="application security engineer",
                goal="Generate a comprehensive remediation plan for security vulnerabilities",
                instructions=[
                    "Explain each vulnerability and its potential impact",
                    "Provide specific remediation steps with code examples",
                    "Suggest preventive measures to avoid similar issues",
                    "Reference relevant OWASP guidelines",
                    "Prioritize by severity (critical first, then high)",
                ],
                constraints=[
                    "Be specific and actionable",
                    "Include code examples where helpful",
                    "Group fixes by severity",
                ],
                input_type="security_findings",
                input_payload=input_payload,
                extra={
                    "risk_score": assessment.get("risk_score", 0),
                    "risk_level": assessment.get("risk_level", "unknown"),
                },
            )
            system = None  # XML prompt includes all context
        else:
            # Use legacy plain text prompts
            system = """You are a security expert in application security and OWASP.
Generate a comprehensive remediation plan for the security findings.

For each finding:
1. Explain the vulnerability and its potential impact
2. Provide specific remediation steps with code examples
3. Suggest preventive measures to avoid similar issues
4. Reference relevant OWASP guidelines

Prioritize by severity (critical first, then high).
Be specific and actionable."""

            user_message = f"""Generate a remediation plan for these security findings:

{input_payload}

Provide a detailed remediation plan with specific fixes."""

        # Try executor-based execution first (Phase 3 pattern)
        if self._executor is not None or self._api_key:
            try:
                step = SECURITY_STEPS["remediate"]
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
                    max_tokens=3000,
                )
        else:
            # Legacy path for backward compatibility
            response, input_tokens, output_tokens = await self._call_llm(
                tier,
                system or "",
                user_message,
                max_tokens=3000,
            )

        # Parse XML response if enforcement is enabled
        parsed_data = self._parse_xml_response(response)

        # Merge crew remediation if available
        if crew_enhanced and crew_remediation:
            response = self._merge_crew_remediation(response, crew_remediation)

        result = {
            "remediation_plan": response,
            "remediation_count": len(critical) + len(high),
            "risk_score": assessment.get("risk_score", 0),
            "risk_level": assessment.get("risk_level", "unknown"),
            "model_tier_used": tier.value,
            "crew_enhanced": crew_enhanced,
        }

        # Add crew-specific fields if enhanced
        if crew_enhanced and crew_remediation:
            result["crew_findings"] = crew_remediation.get("findings", [])
            result["crew_agents_used"] = crew_remediation.get("agents_used", [])

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

        return (result, input_tokens, output_tokens)

    async def _get_crew_remediation(
        self,
        target: str,
        findings: list,
        assessment: dict,
    ) -> dict | None:
        """Get remediation recommendations from SecurityAuditCrew.

        Args:
            target: Path to codebase
            findings: List of findings needing remediation
            assessment: Current assessment dict

        Returns:
            Crew results dict or None if failed

        """
        try:
            from empathy_llm_toolkit.agent_factory.crews import (
                SecurityAuditConfig,
                SecurityAuditCrew,
            )

            from .security_adapters import (
                crew_report_to_workflow_format,
                workflow_findings_to_crew_format,
            )

            # Configure crew for focused remediation
            config = SecurityAuditConfig(
                scan_depth="quick",  # Skip deep scan, focus on remediation
                **self.crew_config,
            )
            crew = SecurityAuditCrew(config=config)

            # Convert findings to crew format for context
            crew_findings = workflow_findings_to_crew_format(findings)

            # Run audit with remediation focus
            context = {
                "focus_areas": ["remediation"],
                "existing_findings": crew_findings,
                "skip_detection": True,  # We already have findings
                "risk_score": assessment.get("risk_score", 0),
            }

            report = await crew.audit(target, context=context)

            if report:
                return crew_report_to_workflow_format(report)
            return None

        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Crew remediation failed: {e}")
            return None

    def _merge_crew_remediation(self, llm_response: str, crew_remediation: dict) -> str:
        """Merge crew remediation recommendations with LLM response.

        Args:
            llm_response: LLM-generated remediation plan
            crew_remediation: Crew results in workflow format

        Returns:
            Merged response with crew enhancements

        """
        crew_findings = crew_remediation.get("findings", [])

        if not crew_findings:
            return llm_response

        # Build crew section efficiently (avoid O(n²) string concat)
        parts = [
            "\n\n## Enhanced Remediation (SecurityAuditCrew)\n\n",
            f"**Agents Used**: {', '.join(crew_remediation.get('agents_used', []))}\n\n",
        ]

        for finding in crew_findings:
            if finding.get("remediation"):
                parts.append(f"### {finding.get('title', 'Finding')}\n")
                parts.append(f"**Severity**: {finding.get('severity', 'unknown').upper()}\n")
                if finding.get("cwe_id"):
                    parts.append(f"**CWE**: {finding.get('cwe_id')}\n")
                if finding.get("cvss_score"):
                    parts.append(f"**CVSS Score**: {finding.get('cvss_score')}\n")
                parts.append(f"\n**Remediation**:\n{finding.get('remediation')}\n\n")

        return llm_response + "".join(parts)

    def _get_remediation_action(self, finding: dict) -> str:
        """Generate specific remediation action for a finding."""
        actions = {
            "sql_injection": "Use parameterized queries or ORM. Never interpolate user input.",
            "xss": "Use framework's auto-escaping. Sanitize user input.",
            "hardcoded_secret": "Move to env vars or use a secrets manager.",
            "insecure_random": "Use secrets.token_hex() or secrets.randbelow().",
            "path_traversal": "Use os.path.realpath() and validate paths.",
            "command_injection": "Use subprocess with shell=False and argument lists.",
        }
        return actions.get(finding.get("type", ""), "Apply security best practices.")


def format_security_report(output: dict) -> str:
    """Format security audit output as a human-readable report.

    This format is designed to be:
    - Easy for humans to read and understand
    - Easy to copy/paste to an AI assistant for remediation help
    - Actionable with clear severity levels and file locations

    Args:
        output: The workflow output dictionary

    Returns:
        Formatted report string

    """
    lines = []

    # Header
    assessment = output.get("assessment", {})
    risk_level = assessment.get("risk_level", "unknown").upper()
    risk_score = assessment.get("risk_score", 0)

    lines.append("=" * 60)
    lines.append("SECURITY AUDIT REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Risk Level: {risk_level}")
    lines.append(f"Risk Score: {risk_score}/100")
    lines.append("")

    # Severity breakdown
    breakdown = assessment.get("severity_breakdown", {})
    lines.append("Severity Summary:")
    for sev in ["critical", "high", "medium", "low"]:
        count = breakdown.get(sev, 0)
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
        lines.append(f"  {icon} {sev.capitalize()}: {count}")
    lines.append("")

    # Files scanned
    files_scanned = output.get("files_scanned", 0)
    lines.append(f"Files Scanned: {files_scanned}")
    lines.append("")

    # Findings requiring review
    needs_review = output.get("needs_review", [])
    if needs_review:
        lines.append("-" * 60)
        lines.append("FINDINGS REQUIRING REVIEW")
        lines.append("-" * 60)
        lines.append("")

        for i, finding in enumerate(needs_review, 1):
            severity = finding.get("severity", "unknown").upper()
            vuln_type = finding.get("type", "unknown")
            file_path = finding.get("file", "").split("Empathy-framework/")[-1]
            line_num = finding.get("line", 0)
            match = finding.get("match", "")[:50]
            owasp = finding.get("owasp", "")
            is_test = finding.get("is_test", False)
            analysis = finding.get("analysis", "")

            test_marker = " [TEST FILE]" if is_test else ""
            lines.append(f"{i}. [{severity}]{test_marker} {vuln_type}")
            lines.append(f"   File: {file_path}:{line_num}")
            lines.append(f"   Match: {match}")
            lines.append(f"   OWASP: {owasp}")
            if analysis:
                lines.append(f"   Analysis: {analysis}")
            lines.append("")

    # Accepted risks
    accepted = output.get("accepted_risks", [])
    if accepted:
        lines.append("-" * 60)
        lines.append("ACCEPTED RISKS (No Action Required)")
        lines.append("-" * 60)
        lines.append("")

        for finding in accepted:
            vuln_type = finding.get("type", "unknown")
            file_path = finding.get("file", "").split("Empathy-framework/")[-1]
            line_num = finding.get("line", 0)
            reason = finding.get("decision_reason", "")

            lines.append(f"  - {vuln_type} in {file_path}:{line_num}")
            if reason:
                lines.append(f"    Reason: {reason}")
        lines.append("")

    # Remediation plan if present
    remediation = output.get("remediation_plan", "")
    if remediation and remediation.strip():
        lines.append("-" * 60)
        lines.append("REMEDIATION PLAN")
        lines.append("-" * 60)
        lines.append("")
        lines.append(remediation)
        lines.append("")

    # Footer with action items
    lines.append("=" * 60)
    if needs_review:
        lines.append("ACTION REQUIRED:")
        lines.append(f"  Review {len(needs_review)} finding(s) above")
        lines.append("  Copy this report to Claude Code for remediation help")
    else:
        lines.append("STATUS: All clear - no critical or high findings")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """CLI entry point for security audit workflow."""
    import asyncio

    async def run():
        workflow = SecurityAuditWorkflow()
        result = await workflow.execute(path=".", file_types=[".py"])

        # Use the new formatted report
        report = format_security_report(result.final_output)
        print(report)

        print("\nCost Report:")
        print(f"  Total Cost: ${result.cost_report.total_cost:.4f}")
        savings = result.cost_report.savings
        pct = result.cost_report.savings_percent
        print(f"  Savings: ${savings:.4f} ({pct:.1f}%)")

    asyncio.run(run())


if __name__ == "__main__":
    main()
