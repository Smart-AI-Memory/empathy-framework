Create a git commit with a well-formatted message following project conventions.

## Execution Steps

### 1. Check Current State

```bash
# See what files have changed
git status

# See the actual changes
git diff

# See staged changes
git diff --cached
```

### 2. Analyze Changes

Review the changes and categorize them:

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation only
- **style**: Formatting, no code change
- **refactor**: Code change that neither fixes bug nor adds feature
- **perf**: Performance improvement
- **test**: Adding or updating tests
- **chore**: Build process, dependencies, etc.

### 3. Stage Files

```bash
# Stage specific files
git add path/to/file.py

# Stage all changes (use carefully)
git add -A

# Interactive staging (if needed)
git add -p
```

### 4. Create Commit Message

Follow conventional commit format:

```
<type>(<scope>): <short summary>

<body - optional>

<footer - optional>
```

**Examples:**

```
feat(auth): Add OAuth2 login support

Implements OAuth2 flow with Google and GitHub providers.
Includes token refresh and session management.

Closes #123
```

```
fix(cache): Resolve race condition in TTL expiration

The cache was incorrectly evicting entries during concurrent access.
Added mutex lock around expiration check.
```

```
refactor(memory): Replace sorted()[:N] with heapq.nlargest()

Performance optimization per list-copy-guidelines.md.
Reduces time complexity from O(n log n) to O(n log k).
```

### 5. Commit

```bash
git commit -m "type(scope): summary"
```

For multi-line messages:
```bash
git commit -m "type(scope): summary" -m "Body paragraph here." -m "Footer here."
```

### 6. Verify

```bash
# Show the commit
git log -1 --stat

# Verify the commit message
git log -1 --format="%B"
```

## Commit Message Guidelines

### Summary Line (Required)
- Max 72 characters
- Use imperative mood ("Add" not "Added")
- No period at end
- Capitalize first letter after type

### Body (Optional)
- Wrap at 72 characters
- Explain "what" and "why", not "how"
- Separate from summary with blank line

### Footer (Optional)
- Reference issues: `Closes #123`, `Fixes #456`
- Breaking changes: `BREAKING CHANGE: description`
- Co-authors: `Co-authored-by: Name <email>`

## Pre-commit Checks

Before committing, the following checks should pass:

```bash
# Run linters
ruff check src/

# Run formatter
black --check src/

# Run tests (optional but recommended)
pytest tests/ -x --no-cov -q
```

If pre-commit hooks are configured:
```bash
pre-commit run --all-files
```

## Common Scenarios

### Amend Last Commit
```bash
git add <files>
git commit --amend --no-edit
```

### Commit with Co-author
```bash
git commit -m "feat: Add feature" -m "Co-authored-by: Name <email@example.com>"
```

### Commit Partial Changes
```bash
git add -p  # Interactive staging
git commit -m "fix: Specific fix"
```

## Related Commands

- `/pr` - Create a pull request
- `/review` - Review code before committing
