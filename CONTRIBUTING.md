# Contributing to API Assistant

Thank you for your interest in contributing to API Assistant! This document provides guidelines for contributors.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Security

For security issues, please see our [Security Overview](docs/security.md) and report vulnerabilities privately to [security@api-assistant.org](mailto:security@api-assistant.org).

## Quick Start

1. **Fork and clone the repository**
2. **Install dependencies**: `poetry install` or `pip install -r requirements.txt`
3. **Run tests**: `make test`
4. **Start development**: `make serve` or `docker-compose up -d`

## Development Commands

```bash
# Start development
make serve                    # Local development
docker-compose up -d         # Docker development

# Testing
make test                    # Run all tests
make test-unit              # Unit tests only
make lint                   # Code linting

# View logs
docker-compose logs -f api-assistant
```

## Making Changes

1. **Create a feature branch**: `git checkout -b feature/your-feature-name`
2. **Make your changes** and add tests
3. **Run tests**: `make test`
4. **Create a Pull Request**

## Testing

```bash
make test              # Run all tests
make test-unit         # Unit tests only
make test-coverage     # With coverage report
```

**Guidelines**: Add tests for new functionality, aim for >90% coverage.

## Pull Request Process

1. **Run checks**: `make test && make lint`
2. **Update documentation** if needed
3. **Create PR** with clear description and linked issues

## Code Style

- **Format**: `make format` (Black + isort)
- **Lint**: `make lint`
- **Type hints**: Required for all functions
- **Docstrings**: Google style

## Commit Messages

Format: `<type>(<scope>): <description>`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example: `feat(auth): add OIDC authentication support`

## Reporting Issues

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:
- Clear description and steps to reproduce
- Environment details (OS, Python version)
- Error messages and stack traces

## Feature Requests

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md) and include:
- Problem statement and proposed solution
- Use cases and alternatives considered

## Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Documentation**: Check the [docs](docs/) folder first

## License

By contributing to API Assistant, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to API Assistant! 🚀 