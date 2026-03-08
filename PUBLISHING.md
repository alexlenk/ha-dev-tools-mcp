# Publishing Guide for ha-dev-tools-mcp

## Status

- ✅ Version 1.0.0 tagged
- ✅ Package built (dist/ directory contains wheel and source distribution)
- ✅ Tag pushed to GitHub
- ⏳ PyPI publishing (requires manual step with credentials)

## PyPI Publishing Instructions

### Prerequisites

1. Create a PyPI account at https://pypi.org/account/register/
2. Generate an API token at https://pypi.org/manage/account/token/
3. Install twine: `python3 -m pip install --user twine`

### Publishing Steps

```bash
# Navigate to the repository
cd release/ha-dev-tools-mcp

# Verify the built packages
ls -la dist/
# Should show:
# - ha_dev_tools_mcp-1.0.0-py3-none-any.whl
# - ha_dev_tools_mcp-1.0.0.tar.gz

# Check the package metadata
python3 -m twine check dist/*

# Upload to PyPI (you'll be prompted for your API token)
python3 -m twine upload dist/*

# Or use environment variable for token
# TWINE_USERNAME=__token__ TWINE_PASSWORD=<your-token> python3 -m twine upload dist/*
```

### Verification

After publishing, verify the package is available:

```bash
# Install from PyPI
pip install ha-dev-tools-mcp

# Test the installation
ha-dev-tools-mcp --version

# Test with uvx (the primary installation method for Kiro)
uvx --from ha-dev-tools-mcp ha-dev-tools-mcp --version
```

### Package Information

- **Package Name**: ha-dev-tools-mcp
- **Version**: 1.0.0
- **PyPI URL**: https://pypi.org/project/ha-dev-tools-mcp/ (after publishing)
- **GitHub**: https://github.com/alexlenk/ha-dev-tools-mcp
- **Entry Point**: `ha-dev-tools-mcp` command

### Troubleshooting

**Issue**: "Invalid or non-existent authentication information"
- **Solution**: Ensure you're using `__token__` as the username and your API token as the password

**Issue**: "File already exists"
- **Solution**: The version has already been published. Increment the version in pyproject.toml and rebuild

**Issue**: "Package name already taken"
- **Solution**: The package name is already registered. This shouldn't happen for ha-dev-tools-mcp

## Next Steps After Publishing

1. Update the README.md with the PyPI badge
2. Test installation via pip and uvx
3. Update the Kiro power to reference the published package
4. Announce the release on relevant channels
