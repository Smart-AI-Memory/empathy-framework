Comprehensive pull request review combining code quality and security analysis.

## Overview

This skill reviews pull requests by analyzing the diff for code quality issues, security vulnerabilities, and providing an actionable verdict. It combines the capabilities of `/review` and `/security-scan` specifically for PR context.

## Execution Steps

### 1. Get PR Information

If PR number provided:
```bash
# Get PR details
gh pr view <number> --json title,body,files,additions,deletions,changedFiles

# Get the diff
gh pr diff <number>

# Get PR comments (for context)
gh pr view <number> --json comments
```

If reviewing local changes:
```bash
# Get diff against main branch
git diff main...HEAD

# List changed files
git diff main...HEAD --name-only

# Get commit messages for context
git log main..HEAD --oneline
```

### 2. Code Quality Review

Analyze the diff for:

#### Style & Standards
- Code formatting consistency
- Naming conventions
- Import organization
- Line length violations

```bash
# Run linters on changed files only
git diff main...HEAD --name-only -- '*.py' | xargs ruff check
git diff main...HEAD --name-only -- '*.py' | xargs black --check --diff
```

#### Code Quality Issues
- Complexity (cyclomatic complexity > 10)
- Duplicate code
- Dead code / unused imports
- Missing type hints
- Missing docstrings on public APIs

#### Logic & Correctness
- Off-by-one errors
- Null/None handling
- Error handling patterns
- Edge cases not covered

### 3. Security Analysis

Check for security issues per OWASP guidelines:

#### Critical (Block PR)
- Hardcoded secrets/credentials
- SQL injection vulnerabilities
- Command injection (shell=True with user input)
- Path traversal (unvalidated file paths)
- eval()/exec() usage

```bash
# Run security scanners on changed files
git diff main...HEAD --name-only -- '*.py' | xargs bandit -ll
```

#### High (Request Changes)
- Bare except: clauses
- Missing input validation
- Insecure deserialization
- Sensitive data in logs

#### Medium (Warn)
- Deprecated function usage
- Missing HTTPS enforcement
- Weak cryptographic choices

### 4. Test Coverage Check

```bash
# Check if tests were added/modified
git diff main...HEAD --name-only | grep -E "test_|_test\.py|tests/"

# Run tests for changed modules
pytest tests/ -x --no-cov -q
```

### 5. Generate Verdict

Based on findings, determine verdict:

| Verdict | Criteria |
|---------|----------|
| **APPROVE** | No blockers, ≤2 minor issues |
| **APPROVE_WITH_SUGGESTIONS** | No blockers, 3-5 minor issues |
| **REQUEST_CHANGES** | 1+ high severity issues or >5 minor issues |
| **REJECT** | 1+ critical security issues |

### 6. Calculate Scores

```
Code Quality Score = 100 - (critical*25 + high*10 + medium*3 + low*1)
Security Risk Score = critical*30 + high*15 + medium*5 + low*1
Combined Score = (Code Quality * 0.6) + ((100 - Security Risk) * 0.4)
```

## Output Format

```
============================================================
PULL REQUEST REVIEW
============================================================

PR: #123 - Add user authentication feature
Branch: feature/auth -> main
Files Changed: 12 (+450, -23)

------------------------------------------------------------
VERDICT: [APPROVE / APPROVE_WITH_SUGGESTIONS / REQUEST_CHANGES / REJECT]
------------------------------------------------------------

Code Quality Score: 85/100
Security Risk Score: 15/100 (Low Risk)
Combined Score: 82/100

------------------------------------------------------------
BLOCKERS (Must Fix)
------------------------------------------------------------
[If any critical issues that block merge]

🔴 src/auth.py:45 - Hardcoded API key detected
   Fix: Move to environment variable

------------------------------------------------------------
CODE QUALITY FINDINGS
------------------------------------------------------------

High Priority:
🟠 src/auth.py:23 - Missing error handling for API call
   Suggestion: Add try/except with specific exceptions

🟠 src/models/user.py:67 - Function complexity too high (CC=15)
   Suggestion: Extract helper methods

Medium Priority:
🟡 src/auth.py:12 - Missing type hints
🟡 src/utils.py:34 - Unused import 'json'

------------------------------------------------------------
SECURITY FINDINGS
------------------------------------------------------------

🟠 src/auth.py:89 - Bare except clause masks errors
   Fix: Catch specific exceptions, add logging

🟡 src/api.py:45 - User input not validated before use
   Suggestion: Add input validation

------------------------------------------------------------
TEST COVERAGE
------------------------------------------------------------

New code coverage: 78%
Tests added: 3
Tests modified: 1
Missing coverage:
  - src/auth.py: lines 45-67
  - src/models/user.py: lines 89-95

------------------------------------------------------------
RECOMMENDATIONS
------------------------------------------------------------

1. Add unit tests for authentication edge cases
2. Consider splitting large auth.py into smaller modules
3. Add rate limiting to login endpoint

------------------------------------------------------------
SUMMARY
------------------------------------------------------------

This PR adds user authentication with OAuth2 support. The implementation
is solid overall with good separation of concerns. Main areas for
improvement are error handling and test coverage for edge cases.

Estimated review time: 15-20 minutes for human reviewer
Auto-fixable issues: 2 (unused imports, formatting)

============================================================
```

## Quick Actions

### Auto-fix Simple Issues
```bash
# Fix formatting
git diff main...HEAD --name-only -- '*.py' | xargs black

# Fix import sorting
git diff main...HEAD --name-only -- '*.py' | xargs ruff check --select I --fix

# Remove unused imports
git diff main...HEAD --name-only -- '*.py' | xargs ruff check --select F401 --fix
```

### Request Changes Comment
Generate a comment for the PR:
```bash
gh pr comment <number> --body "## Review Findings

[Summary of issues]

Please address the blockers before merging."
```

## Related Commands

- `/review` - General code review (not PR-specific)
- `/security-scan` - Deep security analysis
- `/pr` - Create a new pull request
- `/commit` - Create well-formatted commits
