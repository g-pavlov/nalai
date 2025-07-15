# Support

Thank you for using API Assistant! This document provides information about getting help and support.

## Getting Help

### 📚 Documentation First

Before reaching out for support, please check our documentation:

- **[README](README.md)** - Project overview and quick start
- **[Documentation](docs/)** - Complete documentation suite
- **[Security Overview](docs/security.md)** - Security architecture and compliance

### 🔍 Search Existing Issues

Many questions have already been answered. Please search existing issues before creating new ones:

- [GitHub Issues](https://github.com/your-org/integration_assistant/issues)
- [GitHub Discussions](https://github.com/your-org/integration_assistant/discussions)

## Support Channels

### 🐛 Bug Reports
Use our [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)

### 💡 Feature Requests  
Use our [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)

### 🔒 Security Issues
- **DO NOT** create public issues
- **Email**: [security@api-assistant.org](mailto:security@api-assistant.org)
- **See**: [Security Overview](docs/security.md)

### 💬 General Questions
- **GitHub Discussions**: [Community discussions](https://github.com/your-org/integration_assistant/discussions)

## Common Issues

### Installation
```bash
# Python version issues
python --version  # Should be 3.12+

# Dependency issues  
rm -rf .venv && poetry install

# Docker issues
docker-compose down && docker-compose build --no-cache
```

### Configuration
```bash
# Environment setup
make setup-dev

# API specs
ls -la data/api_specs/
```

### Authentication
```bash
# Development mode
export DISABLE_AUTH=true

# Production
export AUTH_OIDC_ISSUER=https://your-domain.auth0.com/
```

### Testing
```bash
# Run tests
make test

# Debug tests
poetry run pytest tests/unit/test_specific_file.py -v -s
```

## Troubleshooting

### Quick Diagnostics
```bash
curl http://localhost:8080/healthz
docker-compose logs api-assistant
```

### Performance
```bash
docker stats
time curl http://localhost:8080/healthz
```

### Security
```bash
tail -f logs/audit.log
curl -H "Authorization: Bearer your-token" http://localhost:8080/api/agent/invoke
```

## Community Support

- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community guidelines
- **GitHub Discussions**: [Community Q&A](https://github.com/your-org/integration_assistant/discussions)

## Professional Support

- **Email**: [enterprise@api-assistant.org](mailto:enterprise@api-assistant.org)
- **Security**: [Security Overview](docs/security.md)

## Stay Updated

- **Releases**: [GitHub Releases](https://github.com/your-org/integration_assistant/releases)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

**Thank you for using API Assistant!** 🚀 