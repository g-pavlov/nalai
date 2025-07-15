# Testing GitHub Actions Workflows Locally

This guide covers how to test GitHub Actions workflows locally using various tools and approaches.

## Overview

Testing GitHub Actions workflows locally helps you:
- **Catch issues early** before pushing to GitHub
- **Reduce CI/CD feedback loops** by testing locally first
- **Debug workflow issues** in your local environment
- **Validate workflow changes** before committing

## Tools for Local Testing

### On-Demand Installation

The project includes automatic, platform-independent installation of required tools:

```bash
# All tools are installed automatically when needed
make test-gh-actions     # Installs gh and act on demand
make setup-dev           # Installs Poetry, Trivy, and other tools
```

The installation system supports:
- **macOS** (Homebrew)
- **Linux** (apt, yum, dnf, pacman, zypper)
- **Windows** (winget, Chocolatey, Scoop)

All tools are installed transparently when commands that need them are run.

### 1. GitHub CLI (`gh`) - Monitor and Manage

GitHub CLI provides commands to interact with GitHub Actions from your terminal.

#### Installation

**Automatic Installation (Recommended):**
```bash
# Tools are installed automatically when needed
make test-gh-actions
```

**Manual Installation:**
```bash
# macOS
brew install gh

# Linux
sudo apt install gh

# Windows
winget install GitHub.cli
```

#### Authentication
```bash
gh auth login
```

#### Key Commands

**List and Monitor Workflows:**
```bash
# List recent workflow runs
gh run list

# List runs for a specific workflow
gh run list --workflow=pr-check.yml

# List runs for a specific branch
gh run list --branch=feature/new-feature

# Watch the latest run in real-time
gh run watch

# Watch a specific run by ID
gh run watch 1234567890

# Watch with detailed logs
gh run watch --log
```

**Manage Workflow Runs:**
```bash
# Re-run the latest failed workflow
gh run rerun

# Re-run a specific workflow by ID
gh run rerun 1234567890

# Re-run with debug logging
gh run rerun --debug

# Download artifacts from the latest run
gh run download

# Download from a specific run
gh run download 1234567890

# Download specific artifacts
gh run download --pattern="*.log"
```

### 2. `act` - Run Workflows Locally

`act` runs GitHub Actions workflows locally using Docker containers.

#### Installation

**Automatic Installation (Recommended):**
```bash
# Tools are installed automatically when needed
make test-gh-actions
```

**Manual Installation:**
```bash
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Windows
choco install act-cli
```

#### Prerequisites
- Docker installed and running
- Sufficient disk space for Docker images

#### Basic Usage

**List Available Workflows:**
```bash
# List all workflows
act -l

# List with more details
act --list
```

**Run Workflows:**
```bash
# Run PR check workflow
act pull_request

# Run feature branch workflow
act push

# Run with specific event
act workflow_dispatch

# Dry run (see what would happen)
act -n

# Verbose output
act --verbose
```

**Configuration:**
```bash
# Use specific secrets
act --secret GITHUB_TOKEN=dummy-token

# Use environment file
act --env-file .env

# Use specific workflow file
act --workflows .github/workflows/pr-check.yml

# Use specific job
act --job lint-and-test
```

#### Advanced Configuration

Create a `.actrc` file for persistent configuration:
```bash
# .actrc
-P uses: actions/setup-python@v4
  image: python:3.12

-P uses: snok/install-poetry@v1
  image: python:3.12

--secret GITHUB_TOKEN=dummy-token
--env REGISTRY=ghcr.io
--env IMAGE_NAME=nalai
```

### 3. Makefile Simulation - Quick Local Testing

Our project includes Makefile targets that simulate CI behavior locally.

#### Available Commands
```bash
# Full CI pipeline simulation
make ci-local

# Individual CI steps
make check              # All checks (CI-safe)
make lint               # Linting (CI-safe)
make test-coverage      # Tests with coverage
make security           # Security scan
make validate-deps      # Dependency validation

# Local development with auto-fix
make check-local        # All checks with auto-fix
make lint-fix           # Linting with auto-fix
```

#### Testing GitHub Actions Tools
```bash
# Run the GitHub Actions testing script
make test-gh-actions
```

## Testing Strategies

### 1. Quick Local Validation (Recommended)

For most development work, use the Makefile approach:

```bash
# Before pushing changes
make check-local        # Run all checks with auto-fix
make ci-local           # Simulate full CI pipeline
```

### 2. Full Workflow Testing

For testing actual workflow files, use `act`:

```bash
# Test PR check workflow
act pull_request

# Test feature branch workflow
act push

# Test with specific inputs
act workflow_dispatch --input version_type=patch
```

### 3. Real Workflow Monitoring

For monitoring actual GitHub runs, use `gh`:

```bash
# Watch your latest push
gh run watch

# Monitor specific workflow
gh run list --workflow=pr-check.yml
gh run watch $(gh run list --workflow=pr-check.yml --limit 1 --json databaseId --jq '.[0].databaseId')
```

## Testing Specific Workflows

### Pull Request Checks

**Local Simulation:**
```bash
make check              # Run the same checks as CI
```

**With act:**
```bash
act pull_request
```

**Monitor Real Runs:**
```bash
gh run list --workflow=pr-check.yml
gh run watch
```

### Feature Branch Pipeline

**Local Simulation:**
```bash
make ci-local           # Includes Docker build
```

**With act:**
```bash
act push
```

**Monitor Real Runs:**
```bash
gh run list --workflow=feature-branch.yml
```

### Release Pipeline

**Local Simulation:**
```bash
make ci-local           # Simulates the build steps
```

**With act:**
```bash
# Test version management
act workflow_dispatch --input version_type=patch

# Test with tag
act push --eventpath .github/events/tag.json
```

**Monitor Real Runs:**
```bash
gh run list --workflow=release-pipeline.yml
```

## Troubleshooting

### Common Issues

**act Issues:**
```bash
# Docker not running
docker --version
docker ps

# Insufficient disk space
df -h

# Permission issues
sudo chmod +x .github/workflows/*.yml
```

**gh CLI Issues:**
```bash
# Not authenticated
gh auth status
gh auth login

# Repository not found
gh repo view
```

**Makefile Issues:**
```bash
# Environment validation
make validate-env

# Check dependencies
make validate-deps
```

### Debug Commands

```bash
# Check act configuration
act -l --verbose

# Check gh authentication
gh auth status

# Check Docker
docker info

# Validate environment
make validate-env
```

## Best Practices

### 1. Development Workflow

1. **Make changes** to code or workflows
2. **Test locally** with `make check-local`
3. **Simulate CI** with `make ci-local`
4. **Test workflow** with `act` (if needed)
5. **Push and monitor** with `gh run watch`

### 2. Workflow Development

1. **Start with Makefile** - Quick validation
2. **Use act for workflow testing** - Full workflow simulation
3. **Monitor with gh** - Real-time feedback
4. **Iterate quickly** - Local testing reduces feedback loops

### 3. CI/CD Pipeline

1. **Local validation** - Catch issues early
2. **Workflow testing** - Ensure workflows work correctly
3. **Real monitoring** - Track actual runs
4. **Quick debugging** - Use local tools for investigation

## Integration with Development

### Pre-commit Hooks

Our git hooks already include local validation:
```bash
# Pre-commit runs automatically
make lint
make validate-deps
```

### IDE Integration

Configure your IDE to run local checks:
- **VS Code**: Add tasks for `make check-local`
- **PyCharm**: Configure external tools for Makefile targets
- **Vim/Neovim**: Use terminal integration

### Continuous Local Testing

For active development, consider:
```bash
# Watch for changes and run checks
fswatch -o . | xargs -n1 -I{} make check-local

# Or use entr for file watching
find . -name "*.py" | entr make check-local
```

## Summary

The combination of tools provides comprehensive local testing:

- **Makefile**: Quick validation and CI simulation
- **act**: Full workflow testing with Docker
- **gh CLI**: Real workflow monitoring and management

This approach ensures you can catch issues locally before they reach GitHub, reducing feedback loops and improving development efficiency. 