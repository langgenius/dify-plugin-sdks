# AGENTS.md

This file provides guidance for agents working with code in this repository.

## Development Commands

### Python SDK Development

**Testing:**
```bash
make test                              # Run all tests
uv run pytest tests/specific_test.py   # Run specific test
```

**Linting and Formatting:**
```bash
make check                             # Check lockfile, formatting, and linting
make lint                              # Check linting only
make format                            # Apply formatting fixes
```

**Documentation Generation:**
```bash
make docs                              # Generate schema documentation
```

**Build and Environment:**
```bash
make dev                               # Sync default dev dependencies
make build                             # Build source and wheel distributions
make clean                             # Remove local build/test artifacts
```

## Project Architecture

### Repository Structure
- **Root Level:** Python SDK package, project metadata, tests, and examples
- **`src/dify_plugin/`:** Main Python SDK implementation
- **`examples/`:** Complete plugin examples (GitHub, OpenAI, Jina, etc.)

### Core SDK Architecture

The Dify Plugin SDK follows a modular architecture with clear separation of concerns:

#### Core Components (`src/dify_plugin/core/`)
- **`runtime.py`:** Session management and backwards invocation system
- **`plugin_executor.py`:** Main execution engine for plugin operations
- **`plugin_registration.py`:** Plugin discovery and registration system
- **`server/`:** Multi-protocol communication layer (stdio, TCP, serverless)

#### Plugin Types (`src/dify_plugin/interfaces/`)
- **`model/`:** AI model integrations (LLM, embedding, TTS, etc.)
- **`tool/`:** Tool providers and individual tools
- **`agent/`:** Agent strategy implementations
- **`endpoint/`:** HTTP endpoint handlers
- **`trigger/`:** Event trigger handlers

#### Communication Patterns
1. **Local Install:** stdio-based communication for development
2. **Remote Install:** TCP-based communication for production deployment
3. **Serverless:** HTTP-based communication for serverless environments

#### Plugin Manifest System
- **`manifest.yaml`:** Plugin metadata and configuration
- **Version Management:** Semantic versioning with compatibility matrix
- **Runtime Configuration:** Memory limits, permissions, language requirements

### Key Architectural Patterns

#### Session-based Runtime
- Each plugin operation runs in a `Session` context
- Sessions provide access to invocations (model, tool, app, storage, file)
- Backwards invocation allows plugins to call Dify services

#### Multi-Modal Communication
- **Full-duplex:** Real-time bidirectional communication (Local/Remote)
- **HTTP streaming:** Server-sent events for serverless environments
- **Blob handling:** Chunked transfer for large binary data

#### Provider-Tool Architecture
- **Providers:** Authentication and configuration management
- **Tools:** Individual operations within a provider
- **Credentials:** OAuth and API key management with validation

## Plugin Examples Structure

Each example in `examples/` follows a consistent structure:
- **`manifest.yaml`:** Plugin metadata
- **`main.py`:** Plugin entry point
- **`provider/`:** Provider configuration and implementation
- **`tools/`:** Individual tool implementations
- **`models/`:** Model configurations (for model providers)
- **`requirements.txt`:** Python dependencies

## Version Management

- **SDK Version:** Currently 0.8.0 (semantic versioning)
- **Manifest Version:** Plugin compatibility version (currently 0.0.2)
- **Minimum Dify Version:** Required Dify version for plugin features

## Development Workflow

1. Use existing examples as templates for new plugins
2. Implement plugin interfaces in the appropriate category
3. Run `make check` before submitting code changes
4. Run `make test` when changes affect runtime behavior, SDK interfaces, or examples
