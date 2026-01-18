Generate and maintain project documentation using the framework's powerful doc-gen capabilities.

## Leverages Existing Features

The Empathy Framework has a sophisticated documentation pipeline:
- **DocumentGenerationWorkflow**: Multi-tier doc generation (Haiku outline → Sonnet write → Opus polish)
- **ManageDocsWorkflow**: Documentation maintenance
- **DocumentationOrchestrator**: Coordinates large-scale doc generation

## Commands

### 1. Generate API Documentation
```bash
empathy workflow run doc-gen --input '{
  "source": "./src",
  "doc_type": "api_reference",
  "audience": "developers"
}'
```

### 2. Generate README
```bash
empathy workflow run doc-gen --input '{
  "source": "./src",
  "doc_type": "readme",
  "audience": "users"
}'
```

### 3. Check Documentation Coverage
```bash
empathy scan . --check-docs
```

Shows:
- Functions without docstrings
- Modules without module-level docs
- Missing type hints
- Outdated documentation

### 4. Generate Docstrings
```bash
empathy workflow run doc-gen --input '{
  "file": "src/utils.py",
  "doc_type": "docstrings",
  "style": "google"
}'
```

### 5. Update Existing Docs
```bash
empathy workflow run manage-docs --input '{
  "action": "update",
  "docs_path": "./docs"
}'
```

## Documentation Types

| Type | Description | Best For |
|------|-------------|----------|
| `api_reference` | Complete API docs | Libraries, SDKs |
| `readme` | Project README | GitHub repos |
| `docstrings` | Function/class docs | Code files |
| `tutorial` | Step-by-step guide | User onboarding |
| `architecture` | System design docs | Technical teams |
| `changelog` | Release notes | Versioned projects |

## Multi-Tier Cost Optimization

The doc-gen workflow optimizes costs:
1. **Outline (Haiku)**: Fast, cheap structure planning
2. **Write (Sonnet)**: Balanced content generation
3. **Polish (Opus)**: Premium final review (skipped for small docs)

Estimated costs:
- Small file docs: ~$0.01
- Module docs: ~$0.05
- Full project docs: ~$0.50-2.00

## Output

After running, provide:
- Documentation coverage before/after
- Files generated/updated
- Cost incurred
- Links to generated docs
- Suggestions for improvement
