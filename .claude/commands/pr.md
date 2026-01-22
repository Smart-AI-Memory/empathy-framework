Create a pull request with a well-structured description.

## Execution Steps

### 1. Verify Branch State

```bash
# Check current branch
git branch --show-current

# Ensure all changes are committed
git status

# Check commits to be included
git log main..HEAD --oneline
```

### 2. Push Branch to Remote

```bash
# Push with upstream tracking
git push -u origin $(git branch --show-current)
```

### 3. Analyze Changes for PR

```bash
# See all changes vs main
git diff main...HEAD --stat

# See commit messages
git log main..HEAD --format="%s"

# Count files changed
git diff main...HEAD --stat | tail -1
```

### 4. Create PR with gh CLI

```bash
gh pr create \
  --title "type(scope): Summary of changes" \
  --body "$(cat <<'EOF'
## Summary
Brief description of what this PR does.

## Changes
- Change 1
- Change 2
- Change 3

## Testing
- [ ] Unit tests pass
- [ ] Manual testing completed
- [ ] No regressions

## Screenshots (if applicable)
[Add screenshots here]

## Related Issues
Closes #XXX
EOF
)"
```

### 5. Alternative: Interactive PR Creation

```bash
gh pr create --web  # Opens browser for PR creation
```

## PR Description Template

```markdown
## Summary
[One paragraph describing the change]

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring (no functional changes)

## Changes Made
- [Specific change 1]
- [Specific change 2]
- [Specific change 3]

## Testing Done
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing performed
- [ ] Edge cases considered

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated (if needed)
- [ ] No new warnings introduced

## Screenshots (if applicable)
[Before/After screenshots]

## Related Issues
Closes #XXX
Relates to #YYY

## Additional Notes
[Any other context or notes for reviewers]
```

## PR Title Conventions

Follow the same format as commit messages:

```
feat(auth): Add OAuth2 support for GitHub login
fix(cache): Resolve TTL race condition
docs(readme): Update installation instructions
refactor(memory): Optimize graph traversal
perf(scanner): Use heapq for top-N queries
test(workflows): Add security audit tests
chore(deps): Update anthropic to 0.40.0
```

## Draft PRs

For work-in-progress:

```bash
gh pr create --draft --title "WIP: Feature name"
```

Mark ready when complete:
```bash
gh pr ready
```

## Review Requests

Request specific reviewers:
```bash
gh pr create --reviewer username1,username2
```

Add reviewers to existing PR:
```bash
gh pr edit --add-reviewer username
```

## Labels

Add labels during creation:
```bash
gh pr create --label "bug,priority:high"
```

Common labels:
- `bug`, `feature`, `documentation`
- `priority:high`, `priority:low`
- `needs-review`, `work-in-progress`
- `breaking-change`

## After PR Creation

### Check PR Status
```bash
gh pr status
gh pr view --web  # Open in browser
```

### Check CI Status
```bash
gh pr checks
```

### Merge When Ready
```bash
gh pr merge --squash --delete-branch
```

## Related Commands

- `/commit` - Create commits before PR
- `/review` - Review code before submitting
- `/test` - Run tests before PR
