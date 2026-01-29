# Acknowledgements

The Empathy Framework stands on the shoulders of giants. This project would not be possible without the incredible work of the open source community. We are deeply grateful to all the developers, maintainers, and contributors of the projects listed below.

---

## Core Framework Dependencies

### Python Type System & Validation

- **[Pydantic](https://github.com/pydantic/pydantic)** - Data validation using Python type annotations. The foundation of our configuration and model validation system.
- **[typing-extensions](https://github.com/python/typing_extensions)** - Backported and experimental type hints for Python.

### Configuration & Environment

- **[python-dotenv](https://github.com/theskumar/python-dotenv)** - Reads key-value pairs from `.env` files and sets them as environment variables.
- **[PyYAML](https://github.com/yaml/pyyaml)** - YAML parser and emitter for Python. Used for workflow configuration.
- **[defusedxml](https://github.com/tiran/defusedxml)** - XML bomb protection for Python stdlib modules.

### Logging & CLI

- **[structlog](https://github.com/hynek/structlog)** - Structured logging for Python. Makes logs readable, parseable, and debuggable.
- **[rich](https://github.com/Textualize/rich)** - Beautiful formatting in the terminal. Powers our progress bars and formatted output.
- **[typer](https://github.com/tiangolo/typer)** - Modern CLI framework based on Python type hints. Makes our CLI intuitive and self-documenting.

---

## AI & LLM Integration

### LLM Providers

- **[Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)** - Official Python SDK for Claude AI. Our primary LLM provider integration.
- **[OpenAI Python SDK](https://github.com/openai/openai-python)** - Official Python SDK for OpenAI's GPT models.
- **[Google Generative AI](https://github.com/google/generative-ai-python)** - Official Python SDK for Google's Gemini models.

### Agent Frameworks

- **[LangChain](https://github.com/langchain-ai/langchain)** - Framework for developing applications powered by language models. Used for our agent workflows.
- **[LangGraph](https://github.com/langchain-ai/langgraph)** - Library for building stateful, multi-actor applications with LLMs. Powers our meta-orchestration.
- **[LangChain Core](https://github.com/langchain-ai/langchain)** - Core abstractions and runtime for LangChain.
- **[LangChain Text Splitters](https://github.com/langchain-ai/langchain)** - Text splitting utilities for LangChain.

### Semantic Search & Embeddings

- **[Sentence Transformers](https://github.com/UKPLab/sentence-transformers)** - Multilingual sentence embeddings. Powers our semantic caching and similarity search.
- **[PyTorch](https://github.com/pytorch/pytorch)** - Deep learning framework. Required for sentence transformers.
- **[NumPy](https://github.com/numpy/numpy)** - Fundamental package for scientific computing with Python.

---

## Memory & Storage

- **[MemDocs](https://pypi.org/project/memdocs/)** - Long-term memory system for AI agents. Provides persistent context across sessions.
- **[Redis](https://github.com/redis/redis-py)** - Python client for Redis. Powers our short-term memory and agent coordination.

---

## Web Framework & API

- **[FastAPI](https://github.com/tiangolo/fastapi)** - Modern, fast web framework for building APIs with Python. Powers our backend API.
- **[Uvicorn](https://github.com/encode/uvicorn)** - Lightning-fast ASGI server. Runs our FastAPI applications.
- **[Starlette](https://github.com/encode/starlette)** - Lightweight ASGI framework/toolkit. Foundation of FastAPI.
- **[HTTPX](https://github.com/encode/httpx)** - Next generation HTTP client for Python. Used in our test suite.

---

## Security & Authentication

- **[bcrypt](https://github.com/pyca/bcrypt/)** - Modern password hashing for your software and your servers.
- **[PyJWT](https://github.com/jpadilla/pyjwt)** - JSON Web Token implementation in Python. Used for authentication tokens.
- **[cryptography](https://github.com/pyca/cryptography)** - Python cryptography library. Required by PyJWT for advanced algorithms.
- **[marshmallow](https://github.com/marshmallow-code/marshmallow)** - Object serialization/deserialization library. Used for secure data validation.

---

## Observability & Telemetry

- **[OpenTelemetry API](https://github.com/open-telemetry/opentelemetry-python)** - OpenTelemetry Python API. Provides vendor-agnostic telemetry.
- **[OpenTelemetry SDK](https://github.com/open-telemetry/opentelemetry-python)** - OpenTelemetry Python SDK. Core implementation of telemetry.
- **[OpenTelemetry OTLP Exporter](https://github.com/open-telemetry/opentelemetry-python)** - OTLP protocol exporter for OpenTelemetry.

---

## Developer Tools

### Code Quality

- **[Black](https://github.com/psf/black)** - The uncompromising Python code formatter. Keeps our code consistent.
- **[Ruff](https://github.com/astral-sh/ruff)** - An extremely fast Python linter, written in Rust. Replaces dozens of linting tools.
- **[mypy](https://github.com/python/mypy)** - Static type checker for Python. Catches type errors before runtime.
- **[Bandit](https://github.com/PyCQA/bandit)** - Security linter for Python. Finds common security issues.
- **[pre-commit](https://github.com/pre-commit/pre-commit)** - Framework for managing git pre-commit hooks. Enforces quality standards.

### Testing

- **[pytest](https://github.com/pytest-dev/pytest)** - Python testing framework. Makes writing tests simple and scalable.
- **[pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)** - Pytest plugin for testing asyncio code.
- **[pytest-cov](https://github.com/pytest-dev/pytest-cov)** - Coverage plugin for pytest. Tracks test coverage.
- **[pytest-xdist](https://github.com/pytest-dev/pytest-xdist)** - Parallel test execution for pytest. Makes test runs 4-8x faster.
- **[pytest-testmon](https://github.com/tarpas/pytest-testmon)** - Selects tests affected by recent changes. Speeds up development.
- **[pytest-picked](https://github.com/anapaulagomes/pytest-picked)** - Runs tests related to unstaged files. Perfect for rapid iteration.
- **[coverage.py](https://github.com/nedbat/coveragepy)** - Code coverage measurement for Python.

---

## Documentation

- **[MkDocs](https://github.com/mkdocs/mkdocs)** - Static site generator for project documentation. Powers our docs site.
- **[Material for MkDocs](https://github.com/squidfunk/mkdocs-material)** - Beautiful, modern theme for MkDocs.
- **[mkdocstrings](https://github.com/mkdocstrings/mkdocstrings)** - Automatic documentation from docstrings.
- **[mkdocs-with-pdf](https://github.com/orzih/mkdocs-with-pdf)** - Generates PDF and ePub from MkDocs documentation.
- **[PyMdown Extensions](https://github.com/facelessuser/pymdown-extensions)** - Extensions for Python Markdown.

---

## Editor Integration

- **[pygls](https://github.com/openlawlibrary/pygls)** - Pythonic Language Server Protocol implementation. Powers our LSP server.
- **[lsprotocol](https://github.com/microsoft/lsprotocol)** - Types and classes for Language Server Protocol.

---

## Platform Compatibility

- **[colorama](https://github.com/tartley/colorama)** - Cross-platform colored terminal text. Makes Windows terminals beautiful.

---

## Document Processing

- **[python-docx](https://github.com/python-openxml/python-docx)** - Creates and updates Microsoft Word (.docx) files. Used in document generation workflows.

---

## Special Thanks

We extend our deepest gratitude to:

### Major Frameworks & Standards

- **[Python Software Foundation](https://www.python.org/)** - For creating and maintaining the Python programming language.
- **[Anthropic](https://www.anthropic.com/)** - For Claude AI and the Model Context Protocol (MCP) specification.
- **[OpenAI](https://openai.com/)** - For pioneering work in large language models and API standards.
- **[The Rust Foundation](https://foundation.rust-lang.org/)** - For Rust, which powers Ruff and many performance-critical tools.

### Community Projects

- **[PyPI](https://pypi.org/)** - The Python Package Index, making package distribution effortless.
- **[GitHub](https://github.com/)** - For hosting our repository and enabling collaboration.
- **[Read the Docs](https://readthedocs.org/)** - For free documentation hosting for open source projects.

### Individual Contributors

We are grateful to all contributors who have submitted issues, pull requests, documentation improvements, and bug reports. Your contributions make this project better every day.

- See [CONTRIBUTORS.md](CONTRIBUTORS.md) for a full list of project contributors.

---

## Contributing Acknowledgements

If you contribute to this project and use open source libraries, please update this file to include proper attribution. Follow these guidelines:

1. **Add the library** to the appropriate section above
2. **Include a link** to the project's homepage or GitHub repository
3. **Provide a brief description** (1-2 sentences) of what the library does and how we use it
4. **Verify the license** is compatible with Apache 2.0 (see [LICENSE](LICENSE))

### How to Add an Acknowledgement

When adding a new dependency:

```bash
# 1. Add to pyproject.toml (already done when you installed it)

# 2. Add to this ACKNOWLEDGEMENTS.md file
# Format:
# - **[Project Name](https://github.com/org/repo)** - Brief description of what it does and how we use it.

# 3. Verify license compatibility
pip-licenses --from=mixed --format=markdown > licenses.md
```

---

## License Compatibility

All dependencies listed here are compatible with the Apache License 2.0 under which Empathy Framework is distributed. Common compatible licenses include:

- MIT License
- Apache License 2.0
- BSD Licenses (2-Clause, 3-Clause)
- Python Software Foundation License
- ISC License

For detailed license information on each dependency, run:

```bash
pip install pip-licenses
pip-licenses --from=mixed --format=markdown
```

---

## Questions?

If you notice a missing attribution or have questions about licensing:

- **Open an issue:** [GitHub Issues](https://github.com/Smart-AI-Memory/empathy-framework/issues)
- **Email us:** admin@smartaimemory.com

---

**Last Updated:** January 29, 2026
**Empathy Framework Version:** 5.1.1

---

*"If I have seen further, it is by standing on the shoulders of giants."* — Isaac Newton

Thank you to everyone who contributes to open source software. Your generosity makes projects like this possible.
