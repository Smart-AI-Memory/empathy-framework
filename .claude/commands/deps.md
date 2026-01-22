Comprehensive dependency audit for security vulnerabilities, outdated packages, and license compliance.

## Overview

This skill performs a thorough dependency analysis using real security tools, not just pattern matching. It checks Python and Node.js dependencies for:
- Known CVEs and security vulnerabilities
- Outdated packages with available updates
- License compliance issues (GPL contamination, etc.)
- Transitive dependency risks

## Execution Steps

### 1. Detect Project Type

First, identify what dependency files exist:

```bash
ls -la requirements*.txt pyproject.toml package.json package-lock.json yarn.lock Pipfile 2>/dev/null
```

### 2. Python Security Audit

If Python dependencies exist (requirements.txt, pyproject.toml, Pipfile):

```bash
# Primary: pip-audit (recommended - uses PyPI advisory database)
pip-audit --format=json 2>/dev/null || pip-audit 2>/dev/null || echo "pip-audit not installed"

# Fallback: safety (if pip-audit unavailable)
safety check --json 2>/dev/null || safety check 2>/dev/null || echo "safety not installed"
```

If neither tool is installed, suggest:
```bash
pip install pip-audit  # Recommended
# OR
pip install safety
```

### 3. Node.js Security Audit

If Node.js dependencies exist (package.json, package-lock.json):

```bash
# npm audit (built-in)
npm audit --json 2>/dev/null || npm audit 2>/dev/null

# For yarn projects
yarn audit --json 2>/dev/null || yarn audit 2>/dev/null
```

### 4. Check for Outdated Packages

```bash
# Python
pip list --outdated --format=json 2>/dev/null || pip list --outdated 2>/dev/null

# Node.js
npm outdated --json 2>/dev/null || npm outdated 2>/dev/null
```

### 5. License Compliance Check

```bash
# Python licenses
pip-licenses --format=json 2>/dev/null || pip-licenses 2>/dev/null || echo "pip-licenses not installed"

# Check for problematic licenses (GPL, AGPL in proprietary projects)
pip-licenses 2>/dev/null | grep -E "GPL|AGPL|LGPL" || echo "No GPL licenses found"
```

If pip-licenses not installed:
```bash
pip install pip-licenses
```

### 6. Generate Report

Compile findings into a structured report:

#### Risk Score Calculation
- Critical vulnerability: +25 points
- High vulnerability: +10 points
- Medium vulnerability: +3 points
- Outdated package: +1 point
- GPL license (in proprietary project): +5 points

#### Risk Levels
- 0-24: LOW (green)
- 25-49: MEDIUM (yellow)
- 50-74: HIGH (orange)
- 75+: CRITICAL (red)

## Output Format

```
============================================================
DEPENDENCY SECURITY REPORT
============================================================

Risk Level: [ICON] [LEVEL]
Risk Score: [X]/100

------------------------------------------------------------
SECURITY VULNERABILITIES
------------------------------------------------------------
[List vulnerabilities by severity: CRITICAL > HIGH > MEDIUM > LOW]

For each vulnerability:
  [ICON] package-name@version
      CVE: CVE-XXXX-XXXXX
      Severity: CRITICAL/HIGH/MEDIUM/LOW
      Fixed in: version
      Description: brief description

------------------------------------------------------------
OUTDATED PACKAGES
------------------------------------------------------------
[List packages with available updates]

  package-name
      Current: X.Y.Z
      Latest: A.B.C
      Type: major/minor/patch

------------------------------------------------------------
LICENSE COMPLIANCE
------------------------------------------------------------
[List any license concerns]

  package-name: GPL-3.0
      Risk: Copyleft license may require source disclosure
      Action: Review usage or find alternative

------------------------------------------------------------
REMEDIATION ACTIONS
------------------------------------------------------------
Priority 1 (URGENT - Security):
  pip install package-name>=fixed-version

Priority 2 (HIGH - Outdated with vulnerabilities):
  pip install --upgrade package-name

Priority 3 (MEDIUM - Maintenance):
  pip install --upgrade package-name

============================================================
```

## Quick Fixes

If critical vulnerabilities found, offer to run:

```bash
# Update all packages with known vulnerabilities
pip install --upgrade [vulnerable-packages]

# Or for Node.js
npm audit fix
```

## CI/CD Integration

For automated checks, suggest adding to CI pipeline:

```yaml
# GitHub Actions example
- name: Security Audit
  run: |
    pip install pip-audit
    pip-audit --strict --desc on
```

## Related Commands

- `/security-scan` - Full security scan including code analysis
- `/test` - Run test suite
- `/release-prep` - Full release preparation including security checks

## Fallback Mode

If no security tools are installed, fall back to the built-in workflow:

```bash
python -m empathy_os.cli workflow run dependency-check --input '{"path": "."}'
```

This uses pattern matching against known vulnerabilities but is less comprehensive than pip-audit/safety.
