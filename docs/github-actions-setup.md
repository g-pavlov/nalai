# GitHub Actions CI/CD Setup

This document describes the GitHub Actions CI/CD pipeline setup for the API Assistant project.

## Overview

### Branch Strategy

This project uses a **protected main branch** with **short-lived feature branches**:

- **Main Branch**: Protected, contains production-ready code
- **Feature Branches**: Short-lived branches for each feature/fix
- **Pull Requests**: All changes to main go through PRs with required reviews
- **Direct to Production**: Merges to main trigger production deployment

### Workflows

The CI/CD pipeline consists of three main workflows:

1. **Pull Request Checks** (`.github/workflows/pr-check.yml`) - Runs on pull requests to main
2. **Feature Branch Pipeline** (`.github/workflows/feature-branch.yml`) - Runs on feature branch pushes
3. **CI/CD Pipeline** (`.github/workflows/ci-cd.yml`) - Runs on pushes to main and manual triggers

## Workflows

### Pull Request Checks

**Trigger**: Pull requests to `main` branch

**Jobs**:
- **lint-and-test**: Runs linting with ruff and unit tests with pytest
- **security-check**: Runs Trivy vulnerability scanner on the codebase

**Purpose**: Ensures code quality and security before merging to main

### Feature Branch Pipeline

**Trigger**: Pushes to any branch except `main` (feature branches)

**Jobs**:
- **lint-and-test**: Runs linting and tests (same as PR checks)
- **build-test**: Builds and tests Docker image locally (not pushed to registry)
- **security-check**: Runs Trivy vulnerability scanner on the codebase

**Purpose**: Validates feature branch changes and ensures Docker builds work

### CI/CD Pipeline

**Trigger**: 
- Pushes to `main` branch
- Pushes of version tags (`v*`)
- Manual workflow dispatch

**Jobs**:
1. **version-management**: Handles semantic versioning with conflict detection
2. **lint-and-test**: Runs linting and tests (same as PR checks)
3. **build-and-push**: Builds and pushes Docker image to GitHub Container Registry
4. **security-scan**: Scans the built Docker image for vulnerabilities
5. **create-release**: Creates GitHub release with changelog and usage instructions

## Version Management

The version management system is based on the GitLab CI version utilities, adapted for GitHub Actions. It follows the same principles as described in `docs/version-management.md`:

### Key Features

- **Manual Version Precedence**: Manual version bumps on feature branches always override automatic increments
- **Backward Targeting Detection**: Prevents creating versions that would create timeline mismatches
- **Conflict Resolution**: Auto-resolves same-level conflicts, requires manual intervention for cross-level conflicts
- **Git Tags as Source of Truth**: Uses git tags as the single source of truth for versioning

### Features

- **Semantic Versioning**: Follows MAJOR.MINOR.PATCH format
- **Conflict Detection**: Detects and handles version conflicts automatically when possible
- **Backward Targeting Detection**: Prevents creating versions that would create timeline mismatches
- **Auto-resolution**: Automatically resolves same-level conflicts
- **Manual Intervention**: Requires human intervention for complex conflicts

### Version Increment Types

- **patch**: Bug fixes and minor changes (1.0.0 → 1.0.1)
- **minor**: New features, backward compatible (1.0.0 → 1.1.0)
- **major**: Breaking changes (1.0.0 → 2.0.0)

### Manual Version Management

You can manually trigger version increments using the workflow dispatch:

1. Go to the Actions tab in GitHub
2. Select "CI/CD Pipeline"
3. Click "Run workflow"
4. Choose the version increment type (patch/minor/major)

### Manual Version Tags

You can also create manual version tags:

```bash
git tag v1.2.3
git push origin v1.2.3
```

This will trigger the CI/CD pipeline with the specified version.

### Feature Branch Version Bumps

For new features or breaking changes, bump the version on your feature branch:

```bash
# For new features
make bump-minor

# For breaking changes  
make bump-major

# Push code and tags together
git add --all && git push origin feature-branch --tags
```

**Note**: Manual version tags on feature branches always override automatic increments when merged to main.

## Docker Images

Docker images are built and pushed to GitHub Container Registry with the following tags:

### Feature Branches (Testing)
- **Commit SHA**: `ghcr.io/owner/repo:abc123` (for testing and development)

### Main Branch (Releases)
- **Semantic Version**: `ghcr.io/owner/repo:1.2.3` (for production releases)
- **Latest**: `ghcr.io/owner/repo:latest` (latest production version)
- **Commit SHA**: `ghcr.io/owner/repo:abc123` (for traceability)

**Note**: Feature branches get Docker images with commit SHA for testing, but only main branch creates semantic version tags for releases.

## Environment Variables

The following secrets are required:

- `GITHUB_TOKEN`: Automatically provided by GitHub Actions
- Any additional secrets for deployment (configure in repository settings)

## Image Publishing

### Production Images

- **Trigger**: Pushes to `main` branch or release tags
- **Purpose**: Publish tagged Docker images to GitHub Container Registry
- **Output**: Production-ready Docker images with semantic version tags

**Note**: This setup publishes production images from the protected main branch. All changes go through pull requests with comprehensive testing before merging to main and publishing images.

## Security

The pipeline includes several security measures:

1. **Code Scanning**: Trivy vulnerability scanner on source code
2. **Container Scanning**: Trivy vulnerability scanner on built Docker images
3. **SARIF Integration**: Results uploaded to GitHub Security tab
4. **Environment Protection**: Production deployments require approval

## Troubleshooting

### Version Conflicts

If you encounter version conflicts:

1. Check the workflow logs for detailed error messages
2. Follow the suggested resolution steps in the error output
3. Create the appropriate version tag manually if needed
4. Re-run the workflow

### Build Failures

Common build failure causes:

1. **Dependency Issues**: Check `pyproject.toml` and `poetry.lock`
2. **Test Failures**: Run tests locally with `poetry run pytest`
3. **Linting Issues**: Run `poetry run ruff check` locally
4. **Docker Build Issues**: Test Docker build locally with `docker build -t test .`

### Image Publishing Issues

1. **Registry Access**: Ensure GitHub Container Registry access is configured
2. **Image Build Failures**: Check Docker build logs for issues
3. **Tag Conflicts**: Verify version tags don't already exist

## Local Development

To test the CI/CD pipeline locally:

```bash
# Install dependencies
poetry install --with=testing

# Run linting
poetry run ruff check src/ tests/
poetry run ruff format --check src/ tests/

# Run tests
poetry run pytest tests/ -v

# Build Docker image
docker build -t api-assistant:test .

# Test Docker image
docker run --rm api-assistant:test --help
```

## Contributing

When contributing to the CI/CD pipeline:

1. Test changes locally first
2. Create a feature branch
3. Submit a pull request
4. Ensure all checks pass
5. Get approval from maintainers

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Semantic Versioning](https://semver.org/)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/) 