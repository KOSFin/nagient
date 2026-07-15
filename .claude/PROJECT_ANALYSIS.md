# Nagient Project Analysis

**Date:** 2026-07-15
**Version:** 0.1.0
**Analysis for:** Production-ready refactoring

## Executive Summary

Nagient is a Python-based agent platform with a plugin architecture for transports, providers, and tools. The main architectural issue is that **bundled components are inconsistently implemented** - some are hardcoded in Python while the system is designed to be manifest-driven.

## Critical Issues Identified

### 1. **Bundled Transports Are Hardcoded (HIGH PRIORITY)**

**Problem:** The Telegram, Console, and Webhook transports have plugin.toml manifests BUT their implementations are hardcoded in `plugins/builtin.py` instead of being loaded through the manifest system.

**Evidence:**
- `src/nagient/bundled_transports/telegram/plugin.toml` exists with full manifest
- `src/nagient/bundled_transports/telegram/transport.py` only imports from builtin: `from nagient.plugins.builtin import TelegramTransportPlugin`
- `src/nagient/plugins/builtin.py` contains ~1200 lines of hardcoded plugin implementations
- `builtin_plugins()` returns only Console and Webhook, NOT Telegram (inconsistent)

**Impact:**
- Bundled transports don't load like user plugins would
- Can't test plugin loading system with bundled examples
- Confusing for developers writing custom transports
- Violates the manifest-driven architecture principle

**Solution:**
1. Remove hardcoded implementations from `plugins/builtin.py`
2. Create proper `transport.py` files for each bundled transport that implement BaseTransportPlugin
3. Ensure bundled transports load through the same registry.discover() path as user plugins
4. The `TelegramTransportPlugin` class should live in `bundled_transports/telegram/transport.py`, not `plugins/builtin.py`

### 2. **Git Integration Issues**

**Problem:** Git tool exists but likely has issues with operations like clone, push, authentication.

**Evidence:**
- `WorkspaceGitToolPlugin` in `tools/builtin.py` (lines 469-878)
- Has credential handling via environment variables
- Uses temporary askpass script for authentication
- But no clone functionality implemented
- User complaint: "не может там что-то склонировать" (can't clone something)

**Solution:**
- Add `workspace.git.clone` function
- Add `workspace.git.push` function  
- Add `workspace.git.pull` function
- Improve error messages
- Add comprehensive tests for Git operations

### 3. **Test Coverage Gaps**

**Problem:** Only 42 test files for ~27,000 lines of code. Need comprehensive coverage.

**Current test structure:**
- `tests/unit/` - unit tests
- `tests/integration/` - integration tests
- `tests/smoke/` - smoke tests

**Missing coverage:**
- Plugin loading (bundled and user plugins)
- Transport authentication and message sending
- Git operations (clone, push, pull)
- Provider authentication flows
- Tool execution and approval workflows

### 4. **Agent Tool Calling System**

**Problem:** Agent tool calls are synchronous and lack predictive response optimization.

**Current state:**
- Tools defined with schemas
- Approval policies: inherit, never, required, policy
- Dry-run support
- But no predictive response templates
- No smart retry logic
- No deferred task support

**Improvements needed:**
- Add response prediction for common operations
- Implement intelligent retry with backoff
- Add progress callbacks for long operations
- Better token economy with caching
- Add "expected outcome" templates

### 5. **Documentation Issues**

**Problems:**
- README is decent but could be more structured
- No SECURITY.md
- No CONTRIBUTING.md  
- Developer docs exist but could be clearer
- No plugin development tutorial
- AI context docs exist but are high-level

**Needed:**
- Comprehensive plugin development guide
- Security best practices document
- Contributing guidelines
- Architecture diagrams
- API reference documentation

### 6. **Build Process**

**Issues to check:**
- pyproject.toml includes too many files in sdist?
- Docker image optimization?
- Release process working correctly?

**Files involved:**
- `pyproject.toml` - build configuration
- `Dockerfile` - container image
- `.github/workflows/` - CI/CD
- `scripts/release/` - release automation

### 7. **Terminal Interface**

**Current state:**
- Interactive setup wizard in `cli.py` (lines 1027-1096)
- Menu-driven configuration
- Color support detection
- Path alias editing

**Issues to verify:**
- All menus work smoothly
- No rendering glitches
- Terminal compatibility
- Error handling in interactive mode

## Architecture Overview

```
nagient/
├── src/nagient/
│   ├── cli.py                  # Main CLI interface (2338 lines)
│   ├── app/                    # Application configuration
│   │   ├── settings.py         # Runtime settings
│   │   ├── configuration.py    # Config loading
│   │   └── container.py        # Dependency injection
│   ├── application/services/   # Business logic services
│   ├── domain/entities/        # Domain models
│   ├── infrastructure/         # External integrations
│   ├── plugins/                # Plugin system
│   │   ├── base.py            # BaseTransportPlugin
│   │   ├── registry.py        # Plugin discovery
│   │   ├── builtin.py         # PROBLEM: Hardcoded implementations
│   │   └── scaffold.py        # Plugin generator
│   ├── bundled_transports/    # Bundled transport plugins
│   │   ├── telegram/          # Has manifest but loads from builtin
│   │   ├── console/           # Has manifest but loads from builtin
│   │   └── webhook/           # Has manifest but loads from builtin
│   ├── bundled_tools/         # Bundled tool plugins
│   │   └── github_api/        # Has manifest + tool.py
│   ├── providers/             # LLM provider plugins
│   ├── tools/                 # Tool system
│   │   ├── base.py           # BaseToolPlugin
│   │   ├── builtin.py        # Built-in tools (2110 lines)
│   │   └── registry.py       # Tool discovery
│   ├── workspace/             # Workspace management
│   └── security/              # Security and approvals
├── tests/
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── smoke/                 # Smoke tests
├── docs/                      # Documentation
├── developer/                 # Developer guide
└── ai/                        # AI context docs
```

## Plugin System Design

**Manifest-driven architecture:**
1. Each plugin has a `plugin.toml` or `tool.toml` manifest
2. Manifest declares: id, version, functions, config, secrets
3. Registry discovers plugins from directories
4. Entrypoint file exports `build_plugin()` factory
5. Factory returns an instance of Base*Plugin

**Current inconsistency:**
- Bundled transports have manifests ✓
- Bundled transports have transport.py ✗ (just imports from builtin)
- User plugins would load correctly ✓
- Bundled plugins don't follow same path ✗

## Code Quality Metrics

- **Total lines:** ~27,000
- **Test files:** 42
- **Estimated coverage:** 40-50% (needs measurement)
- **Linting:** Uses ruff
- **Type checking:** Uses mypy with strict mode
- **Python version:** 3.11+

## Recommendations

### Phase 1: Fix Architecture (HIGH PRIORITY)
1. Refactor bundled transports to use manifest system
2. Remove hardcoded implementations from plugins/builtin.py
3. Ensure Telegram/Console/Webhook load like user plugins
4. Add comprehensive tests for plugin loading

### Phase 2: Fix Git Integration
1. Add clone, push, pull functions
2. Improve authentication handling
3. Better error messages
4. Add tests for all Git operations

### Phase 3: Improve Agent System
1. Add predictive response templates
2. Implement retry logic
3. Add progress callbacks
4. Optimize token usage

### Phase 4: Documentation
1. Write SECURITY.md
2. Write CONTRIBUTING.md
3. Create plugin development guide
4. Add architecture diagrams
5. Improve README structure

### Phase 5: Testing
1. Achieve 80%+ test coverage
2. Add integration tests for all major flows
3. Add end-to-end tests
4. Performance testing

### Phase 6: Release
1. Clean up pyproject.toml
2. Verify Docker build
3. Test release process
4. Bump version
5. Tag and publish

## Next Steps

1. ✓ Complete this analysis
2. Start with Phase 1: Fix bundled transport architecture
3. Create comprehensive test suite
4. Update all documentation
5. Prepare production release
