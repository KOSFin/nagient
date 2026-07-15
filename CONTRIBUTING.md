# Contributing to Nagient

Thank you for your interest in contributing to Nagient! This guide will help you get started.

## Code of Conduct

Be respectful, collaborative, and constructive. We welcome contributions from everyone.

## How to Contribute

### Reporting Bugs

**Before submitting:**
- Check existing issues to avoid duplicates
- Test with the latest version
- Gather reproduction steps

**When submitting:**
- Use a clear, descriptive title
- Provide detailed reproduction steps
- Include system information (OS, Python version)
- Add relevant logs from `~/.nagient/logs/`

### Suggesting Features

**Good feature requests include:**
- Clear use case and problem statement
- Proposed solution or approach
- Alternative solutions considered
- Impact on existing functionality

### Code Contributions

#### Getting Started

1. **Fork the repository**
2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/nagient.git
   cd nagient
   ```

3. **Set up development environment:**
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -e '.[dev]'
   ```

4. **Create a branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

#### Development Workflow

1. **Make your changes**
2. **Write tests** for new functionality
3. **Run quality checks:**
   ```bash
   # Run tests
   pytest tests/ -v
   
   # Check coverage
   pytest tests/ --cov=src/nagient --cov-report=html
   
   # Lint code
   ruff check src tests
   
   # Type check
   mypy src
   ```

4. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

5. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request** on GitHub

#### Commit Message Format

Use conventional commits:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions or changes
- `refactor:` Code refactoring
- `chore:` Build, dependencies, or tooling

**Examples:**
```
feat(transport): add Slack transport plugin
fix(git): handle authentication errors properly
docs(plugin): add plugin development guide
test(registry): add plugin discovery tests
```

## Development Guidelines

### Code Style

- **Python 3.11+** syntax and features
- **Type hints** for all functions and methods
- **PEP 8** style (enforced by ruff)
- **Docstrings** for public APIs
- **Line length:** 100 characters max

### Project Structure

```
nagient/
├── src/nagient/          # Source code
│   ├── bundled_transports/  # Bundled transport plugins
│   ├── bundled_tools/       # Bundled tool plugins
│   ├── plugins/             # Plugin system
│   ├── providers/           # LLM provider integrations
│   ├── tools/               # Tool system
│   ├── application/         # Business logic
│   ├── domain/              # Domain models
│   ├── infrastructure/      # External integrations
│   └── cli.py               # CLI interface
├── tests/                # Test suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── smoke/           # Smoke tests
├── docs/                 # Documentation
├── developer/            # Developer guides
└── scripts/              # Build and release scripts
```

### Testing

**Write tests for:**
- All new features
- Bug fixes (test should fail before fix, pass after)
- Edge cases and error handling
- Public API changes

**Test organization:**
- Unit tests in `tests/unit/`
- Integration tests in `tests/integration/`
- Smoke tests in `tests/smoke/`

**Coverage target:** 80%+ for new code

### Plugin Development

#### Creating a Transport Plugin

1. **Create plugin directory:**
   ```bash
   mkdir -p ~/.nagient/plugins/my-transport
   cd ~/.nagient/plugins/my-transport
   ```

2. **Create `plugin.toml`:**
   ```toml
   id = "custom.my-transport"
   type = "transport"
   version = "0.1.0"
   display_name = "My Transport"
   namespace = "mytransport"
   runtime = "python"
   entrypoint = "transport.py"
   instructions_file = "instructions.md"
   
   [required_slots]
   send_message = "mytransport.sendMessage"
   send_notification = "mytransport.sendNotification"
   normalize_inbound_event = "mytransport.normalizeInboundEvent"
   poll_inbound_events = "mytransport.pollInboundEvents"
   healthcheck = "mytransport.healthcheck"
   selftest = "mytransport.selftest"
   start = "mytransport.start"
   stop = "mytransport.stop"
   
   [function_bindings]
   "mytransport.sendMessage" = "send_message"
   "mytransport.sendNotification" = "send_notification"
   # ... etc
   ```

3. **Create `transport.py`:**
   ```python
   from nagient.plugins.base import BaseTransportPlugin
   
   class MyTransportPlugin(BaseTransportPlugin):
       def send_message(self, payload):
           # Implementation
           pass
       
       # Implement other required methods
   
   def build_plugin():
       return MyTransportPlugin()
   ```

4. **Reference bundled transports** as examples:
   - `src/nagient/bundled_transports/telegram/` - Full-featured example
   - `src/nagient/bundled_transports/console/` - Minimal example
   - `src/nagient/bundled_transports/webhook/` - HTTP example

#### Creating a Tool Plugin

Similar to transport plugins, but use `tool.toml` and inherit from `BaseToolPlugin`.

See `src/nagient/bundled_tools/github_api/` for a complete example.

### Documentation

**Update documentation when:**
- Adding new features
- Changing APIs
- Modifying configuration
- Adding dependencies

**Documentation locations:**
- User docs: `docs/`
- Developer docs: `developer/`
- API docs: Inline docstrings
- Examples: `docs/examples/`

## Pull Request Process

1. **Update CHANGELOG.md** with your changes
2. **Ensure all tests pass** and coverage is maintained
3. **Update documentation** if needed
4. **Squash commits** if you have many small commits
5. **Request review** from maintainers

### PR Review Checklist

- [ ] Tests pass
- [ ] Code coverage maintained or improved
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Commit messages follow convention
- [ ] No merge conflicts
- [ ] Code style follows guidelines

## Release Process

Releases are automated via GitHub Actions:

1. **Update version** in `src/nagient/version.py`
2. **Update CHANGELOG.md** with release notes
3. **Commit and push** to `main` branch
4. **Auto-tag workflow** creates git tag `vX.Y.Z`
5. **Release workflow** builds and publishes artifacts
6. **Update center** publishes installers

## Architecture Principles

### Manifest-Driven

All plugins (bundled and user) load via manifests. No hardcoded plugins.

### Discovery-Based

Plugin registry discovers plugins from directories, no manual registration.

### Factory Pattern

Plugins export `build_plugin()` function, registry calls it to instantiate.

### Separation of Concerns

- `domain/` - Pure business logic
- `application/` - Use cases and services
- `infrastructure/` - External integrations
- `plugins/` - Plugin system

### Type Safety

Use type hints everywhere, enforce with mypy in strict mode.

## Getting Help

- **Documentation:** [docs/README.md](docs/README.md)
- **Architecture:** [docs/architecture.md](docs/architecture.md)
- **Examples:** Bundled plugins in `src/nagient/bundled_*/`
- **Issues:** [GitHub Issues](https://github.com/YOUR_ORG/nagient/issues)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

*Thank you for contributing to Nagient!*
