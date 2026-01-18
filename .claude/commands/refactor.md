Plan and execute refactoring safely with the framework's refactor-plan workflow.

## Commands

### 1. Generate Refactoring Plan
```bash
empathy workflow run refactor-plan --input '{
  "target": "./src/legacy_module.py",
  "goal": "improve maintainability"
}'
```

### 2. Analyze Code for Refactoring Opportunities
```bash
empathy workflow run code-review --input '{
  "path": "./src",
  "focus": "refactoring"
}'
```

## Refactoring Types

| Type | Description | Risk |
|------|-------------|------|
| Rename | Variables, functions, classes | Low |
| Extract | Method, class, module | Medium |
| Inline | Remove unnecessary abstraction | Medium |
| Move | Relocate to better module | Medium |
| Restructure | Change architecture | High |

## Safe Refactoring Process

### Step 1: Analysis
- Identify code smells
- Map dependencies
- Find affected tests

### Step 2: Planning
- Break into small, reversible steps
- Identify risks at each step
- Plan test coverage

### Step 3: Execution
- One change at a time
- Run tests after each change
- Commit frequently

### Step 4: Validation
- All tests pass
- No regression in behavior
- Code coverage maintained

## Code Smells Detected

The framework identifies:
- **Long methods** (>50 lines)
- **Large classes** (>500 lines)
- **Deep nesting** (>4 levels)
- **Duplicate code** (>10 lines repeated)
- **Feature envy** (method uses another class more than its own)
- **God objects** (class knows too much)
- **Shotgun surgery** (one change affects many files)

## Output Format

For each refactoring opportunity:

```markdown
## Refactoring: Extract Authentication Logic

**Target:** src/views/login.py:45-120
**Type:** Extract Method → Extract Class
**Risk:** Medium

### Current Issues
- Authentication logic mixed with view logic
- 75 lines of code in single function
- Hard to test in isolation

### Proposed Changes
1. Extract `authenticate_user()` method (lines 50-80)
2. Create `AuthenticationService` class
3. Move to `src/services/auth.py`
4. Update imports in affected files

### Affected Tests
- tests/test_login.py (update imports)
- tests/test_auth.py (add new tests)

### Execution Steps
1. [ ] Create AuthenticationService class
2. [ ] Move authentication logic
3. [ ] Update login view to use service
4. [ ] Run tests: `pytest tests/test_login.py tests/test_auth.py`
5. [ ] Commit: "refactor: Extract AuthenticationService"
```

## Safety Checklist

Before refactoring:
- [ ] Tests exist for affected code
- [ ] Tests are passing
- [ ] Changes are committed (clean working tree)
- [ ] Refactoring plan reviewed

After refactoring:
- [ ] All tests pass
- [ ] No new linting errors
- [ ] Coverage not decreased
- [ ] Changes committed with clear message
