Start an interactive Socratic workflow builder session.

Guide users through creating optimized agent workflows using guided questioning.

## Process

1. **Capture Goal**
   Ask: "What would you like to accomplish? Describe your goal in a few sentences."

2. **Analyze & Detect Domain**
   - Parse the goal for keywords (code review, security, testing, documentation, etc.)
   - Identify programming languages mentioned
   - Detect quality focus areas

3. **Ask Clarifying Questions**
   Based on domain, ask targeted questions:
   - **Code Review**: What languages? Focus on security/performance/style?
   - **Security**: Compliance requirements? OWASP focus areas?
   - **Testing**: Unit/integration/e2e? Coverage targets?
   - **Documentation**: API docs? User guides? Code comments?

4. **Generate Workflow**
   Once requirements are clear, generate:
   - Agent blueprints with roles and tools
   - Workflow stages with dependencies
   - Success criteria with measurable metrics

5. **Present Results**
   Show:
   - Generated agents and their responsibilities
   - Workflow execution order
   - How success will be measured
   - Option to save or execute

## Example Interaction

```
User: I want to automate code reviews for my Python project

Claude: I'll help you create a code review workflow. A few questions:

1. **Quality Focus**: What aspects matter most?
   [ ] Security vulnerabilities
   [ ] Performance issues
   [ ] Code style/consistency
   [ ] Test coverage
   [ ] Documentation

2. **Review Depth**: How thorough?
   - Quick scan (fast, catches obvious issues)
   - Standard review (balanced)
   - Deep analysis (thorough, slower)

3. **Output Format**: How should results be delivered?
   - Markdown report
   - GitHub PR comments
   - JSON for CI integration
```

## Storage

Sessions are saved to `.empathy/socratic/sessions/` for resuming later.
Blueprints are saved to `.empathy/socratic/blueprints/` for reuse.

## Related Commands

- `/status` - Check project status
- `/test` - Run test suite after workflow completion
