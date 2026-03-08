# Contributing to HA Dev Tools MCP Server

Thank you for your interest in contributing to the HA Dev Tools MCP Server! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

This project follows a standard code of conduct. Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.12 or later
- Git
- A GitHub account
- Home Assistant instance for testing (optional but recommended)

### Finding Issues to Work On

- Check the [Issues](https://github.com/username/ha-dev-tools-mcp/issues) page
- Look for issues labeled `good first issue` or `help wanted`
- Comment on an issue to let others know you're working on it

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/ha-dev-tools-mcp.git
cd ha-dev-tools-mcp

# Add upstream remote
git remote add upstream https://github.com/username/ha-dev-tools-mcp.git
```

### 2. Create Virtual Environment

```bash
# Create virtual environment with Python 3.12+
python3.12 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

```bash
# Install package in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
python -c "import ha_dev_tools; print(ha_dev_tools.__version__)"
```

### 4. Set Up Pre-commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install
```

## Development Workflow

### 1. Create a Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

### 2. Make Changes

- Write clear, readable code
- Follow the existing code style
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_your_feature.py -v

# Run with coverage
pytest tests/ --cov=ha_dev_tools --cov-report=html
```

### 4. Commit Your Changes

```bash
# Stage your changes
git add .

# Commit with a descriptive message
git commit -m "Add feature: brief description"
```

See [Commit Guidelines](#commit-guidelines) for commit message format.

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/test_*.py -v -k "not integration"

# Run property-based tests
pytest tests/test_*_properties.py -v

# Run integration tests (requires HA instance)
pytest tests/integration/ -v

# Run with coverage report
pytest tests/ --cov=ha_dev_tools --cov-report=html --cov-report=term
```

### Writing Tests

- **Unit tests**: Test individual functions and classes in isolation
- **Property-based tests**: Use Hypothesis to test universal properties
- **Integration tests**: Test end-to-end workflows with real HA instance

Example unit test:

```python
import pytest
from ha_dev_tools.validation import validate_file_path, ValidationError

def test_validate_file_path_rejects_traversal():
    """Test that path traversal is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        validate_file_path("../etc/passwd")
    
    assert "path traversal" in str(exc_info.value).lower()
```

Example property-based test:

```python
from hypothesis import given, strategies as st
from ha_dev_tools.validation import validate_positive_integer

@given(value=st.integers(min_value=1, max_value=1000000))
def test_validate_positive_integer_accepts_positive(value):
    """Property: All positive integers should be accepted."""
    validate_positive_integer(value, "test_param")  # Should not raise
```

### Test Coverage

- Aim for at least 80% code coverage
- All new features must include tests
- Bug fixes should include regression tests

## Code Style

### Python Style Guide

This project follows [PEP 8](https://pep8.org/) with some modifications:

- Line length: 100 characters (not 79)
- Use double quotes for strings
- Use type hints for all function signatures

### Formatting Tools

```bash
# Format code with Black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Lint with Ruff
ruff check src/ tests/

# Type checking with mypy
mypy src/
```

### Code Quality Checklist

Before submitting a PR, ensure:

- [ ] Code is formatted with Black
- [ ] Imports are sorted with isort
- [ ] No linting errors from Ruff
- [ ] Type hints are present and mypy passes
- [ ] All tests pass
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated (if applicable)

## Commit Guidelines

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```bash
# Good commit messages
git commit -m "feat: Add template validation with entity checking"
git commit -m "fix: Handle timeout errors in API client"
git commit -m "docs: Update README with installation instructions"
git commit -m "test: Add property-based tests for file operations"

# Bad commit messages (avoid these)
git commit -m "Update"
git commit -m "Fix bug"
git commit -m "Changes"
```

### Commit Best Practices

- Use imperative mood ("Add feature" not "Added feature")
- Keep subject line under 72 characters
- Separate subject from body with blank line
- Explain what and why, not how
- Reference issues: "Fixes #123" or "Relates to #456"

## Pull Request Process

### 1. Update Your Branch

```bash
# Fetch latest changes from upstream
git fetch upstream

# Rebase your branch on upstream/main
git rebase upstream/main

# Resolve any conflicts if needed
```

### 2. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 3. Create Pull Request

1. Go to the [repository](https://github.com/username/ha-dev-tools-mcp)
2. Click "New Pull Request"
3. Select your fork and branch
4. Fill out the PR template:
   - Clear title describing the change
   - Description of what changed and why
   - Link to related issues
   - Screenshots/examples if applicable

### 4. PR Review Process

- Maintainers will review your PR
- Address any feedback or requested changes
- Keep the PR updated with main branch
- Once approved, a maintainer will merge your PR

### PR Checklist

Before submitting, ensure:

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages follow guidelines
- [ ] PR description is clear and complete
- [ ] No merge conflicts with main branch

## Reporting Issues

### Bug Reports

When reporting bugs, include:

- **Description**: Clear description of the bug
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened
- **Environment**:
  - Python version
  - Package version
  - Home Assistant version
  - Operating system
- **Logs**: Relevant error messages or logs
- **Additional Context**: Screenshots, configuration, etc.

### Feature Requests

When requesting features, include:

- **Description**: Clear description of the feature
- **Use Case**: Why this feature would be useful
- **Proposed Solution**: How you envision it working
- **Alternatives**: Other approaches you've considered
- **Additional Context**: Examples, mockups, etc.

## Development Tips

### Debugging

```bash
# Run with verbose logging
PYTHONPATH=src python -m ha_dev_tools.server --log-level DEBUG

# Use pdb for debugging
import pdb; pdb.set_trace()

# Use pytest with pdb
pytest tests/test_file.py -v --pdb
```

### Testing with Real Home Assistant

```bash
# Set environment variables
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_long_lived_access_token"

# Run integration tests
pytest tests/integration/ -v
```

### Working with MCP Inspector

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Run server with inspector
mcp-inspector python -m ha_dev_tools.server
```

## Related Projects

When contributing, you may also need to work with:

- **[HA Dev Tools Integration](https://github.com/username/ha-dev-tools)** - The Home Assistant custom integration
- **[HA Development Power](https://github.com/username/ha-development-power)** - The Kiro Power package

## Questions?

- Open a [Discussion](https://github.com/username/ha-dev-tools-mcp/discussions)
- Join our community chat (if available)
- Check existing [Issues](https://github.com/username/ha-dev-tools-mcp/issues)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to HA Dev Tools MCP Server! 🎉
