Check dependency health, security vulnerabilities, and update recommendations.

## Commands

### 1. Run Dependency Check Workflow
```bash
empathy workflow run dependency-check --input '{"path": "."}'
```

### 2. Security Vulnerability Scan
```bash
# Using pip-audit
pip-audit

# Using safety (if installed)
safety check
```

### 3. Check for Outdated Packages
```bash
pip list --outdated
```

### 4. License Compatibility Check
```bash
# Using pip-licenses (if installed)
pip-licenses --summary
```

### 5. Dependency Tree
```bash
pipdeptree
```

## Analysis

### Security Report

| Package | Current | Vulnerability | Severity | Fix Version |
|---------|---------|---------------|----------|-------------|
| requests | 2.28.0 | CVE-2023-XXXX | HIGH | 2.31.0 |
| ... | ... | ... | ... | ... |

### Outdated Packages

| Package | Current | Latest | Type |
|---------|---------|--------|------|
| pytest | 7.4.0 | 8.0.0 | Major |
| black | 23.12 | 24.1 | Minor |
| ... | ... | ... | ... |

### License Summary

| License | Count | Packages |
|---------|-------|----------|
| MIT | 45 | requests, click, ... |
| Apache 2.0 | 12 | ... |
| GPL | 2 | ⚠️ Review needed |

## Recommendations

Based on the analysis:

1. **Critical Updates** (security vulnerabilities)
   ```bash
   pip install --upgrade package1 package2
   ```

2. **Recommended Updates** (bug fixes, minor versions)
   ```bash
   pip install --upgrade package3 package4
   ```

3. **Review Needed** (major versions, breaking changes)
   - Check CHANGELOG before updating
   - Run tests after update

4. **License Concerns**
   - GPL packages may have viral licensing implications
   - Review compatibility with your project license

## Automation

Add to CI/CD:
```yaml
# .github/workflows/deps.yml
- name: Check dependencies
  run: |
    pip-audit --strict
    empathy workflow run dependency-check
```

## Output

Provide actionable summary:
- Critical vulnerabilities: X (fix immediately)
- Outdated packages: X
- License issues: X
- Recommended actions with commands
