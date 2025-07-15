---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: ['bug', 'needs-triage']
assignees: ''
---

## Bug Description

A clear and concise description of what the bug is.

## Steps to Reproduce

1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected Behavior

A clear and concise description of what you expected to happen.

## Actual Behavior

A clear and concise description of what actually happened.

## Environment

- **OS**: [e.g., Ubuntu 20.04, macOS 14.0, Windows 11]
- **Python Version**: [e.g., 3.12.8]
- **Package Version**: [e.g., api-assistant 1.0.0]
- **Docker Version**: [e.g., 24.0.0] (if using Docker)
- **Browser**: [e.g., Chrome 120.0] (if applicable)

## Additional Context

Add any other context about the problem here, such as:
- Screenshots
- Error messages and stack traces
- Configuration files
- Related issues

## Checklist

- [ ] I have searched existing issues to avoid duplicates
- [ ] I have provided all required information
- [ ] I have included error messages and stack traces
- [ ] I have tested with the latest version
- [ ] I have provided steps to reproduce the issue

## Logs

If applicable, please include relevant logs:

```bash
# Application logs
docker-compose logs api-assistant

# Error logs
tail -f logs/error.log

# Debug logs
tail -f logs/debug.log
```

## Configuration

If the issue is configuration-related, please include your configuration:

```bash
# Environment variables (remove sensitive data)
env | grep -E "(API_ASSISTANT|AUTH|CACHE|AUDIT)"

# Configuration file
cat config.yaml
``` 