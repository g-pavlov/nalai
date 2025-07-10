# Development Testing Scenarios

This document outlines **development-specific scenarios** and troubleshooting workflows for the AI Gateway development environment.

## 🚀 Quick Start

```bash
make setup    # Setup development environment
make serve    # Start development server with hot reload
make build    # Build development Docker image

# Alternative: Using Docker Compose
docker-compose up --build  # Start with hot reload
docker-compose up -d       # Start in background
```

## 🔧 Development Workflow Scenarios

### Scenario 1: New Developer Setup
```bash
# 1. Clone and setup
git clone <repository-url>
cd ai-gateway
make setup

# 2. Configure environment
# Edit .env with your credentials (see README.md for details)

# 3. Start development (choose one)
make serve      # Using Makefile
docker-compose up --build     # Using Docker Compose
```

### Scenario 2: Adding New Modules
```bash
# 1. Create module structure
mkdir src/api_assistant/my-new-module
touch src/api_assistant/my-new-module/__init__.py

# 2. Add to main dependencies (if needed)
# Edit pyproject.toml in project root

# 3. Install and test
make setup
make test
```

### Scenario 3: Debugging Build Issues
```bash
# 1. Check environment
grep -E "(AUTH0)" .env

# 2. Check build logs
docker build -f Dockerfile.dev -t ai-gateway:dev . 2>&1 | tee build.log

# 3. Check Docker images
docker images | grep ai-gateway
```

### Scenario 4: Testing Production Build
```bash
# 1. Build production image
make build-prod

# 2. Run production container (choose one)
make serve-prod               # Using Makefile
docker run --rm -p 8080:8080 --env-file .env ai-gateway:prod  # Direct Docker

# 3. Test with production config
curl http://localhost:8080/health
```

### Scenario 5: Docker Compose Development Workflow
```bash
# 1. Start development environment
docker-compose up --build

# 2. Start in background
docker-compose up -d

# 3. View logs
docker-compose logs -f

# 4. Access container shell
docker-compose exec app /bin/bash

# 5. Stop services
docker-compose down

# 6. Rebuild and restart
docker-compose up --build --force-recreate
```

## 🧪 Testing Scenarios

### Linting and Code Quality
```bash
# Check code quality
make lint

# Fix auto-fixable issues
make lint-fix

# Check dependencies
make lint-deps
```

### Docker Build Testing
```bash
# Build development image
make build

# Build production image
make build-prod

# Using Docker Compose
docker-compose build          # Build development image
docker-compose build --no-cache  # Force rebuild

# Check image details
docker images | grep ai-gateway
```

## 🔍 Troubleshooting Scenarios

### Issue 1: Missing .env file
**Symptoms**: Build fails with "AUTH0_CLIENT_ID not found"
**Solution**: 
```bash
make setup  # Creates .env file
# Edit .env with your actual credentials
```

### Issue 2: Auth0 Authentication Failures
**Symptoms**: Docker build fails with authentication errors
**Solution**:
- Ensure `AUTH0_CLIENT_ID` and `AUTH0_CLIENT_SECRET` are set in `.env`
- Verify credentials are valid in Auth0

### Issue 3: Import Errors in Tests
**Symptoms**: `ModuleNotFoundError` in test runs
**Solution**:
```bash
make setup  # Install dependencies
poetry show  # Check installed packages
```

### Issue 4: API Specifications Not Found
**Symptoms**: Runtime errors about missing API specs
**Solution**:
- **Location**: `src/api_assistant/api_specs/`
- **Runtime access**: Via `importlib.resources`
- **Package data**: Automatically included in Docker images

### Issue 5: Docker Build Performance Issues
**Symptoms**: Slow builds or cache misses
**Solution**:
```bash
# Check build logs
docker build -f Dockerfile.dev -t ai-gateway:dev . 2>&1 | tee build.log

# Check layer caching
docker system df
docker builder prune  # Clean build cache if needed
```

### Issue 6: Production Container Troubleshooting
**Symptoms**: Need to debug running production container
**Solution**:
```bash
# 1. Find running container
docker ps | grep ai-gateway

# 2. Access container shell (if running)
docker exec -it <container_id> /bin/bash

# 3. Or start container with shell access
docker run --rm -it --entrypoint /bin/bash -p 8080:8080 --env-file .env ai-gateway:prod

# 4. Check logs
docker logs <container_id>
docker logs -f <container_id>  # Follow logs

# 5. Copy files from container
docker cp <container_id>:/app/logging.yaml ./container_logging.yaml

# 6. Inspect container filesystem
docker exec -it <container_id> ls -la /app
docker exec -it <container_id> cat /app/logging.yaml
```

## 🔒 Security Best Practices

### Environment Variables
- Never commit `.env` files
- Use `.env.example` for documentation
- Rotate credentials regularly
- **Fail-fast validation**: Required variables checked before builds

### Dependencies
- Regular security updates with `poetry audit`
- Pin dependency versions in `pyproject.toml`
- **Public Registry**: Standard PyPI package management

### Docker Security
- Use multi-stage builds (production)
- Minimize image layers
- Run as non-root user in production
- **Build tools cleanup**: Remove unnecessary tools after installation



## 🔧 Debug Commands

```bash
# Environment validation
grep -E "(AUTH0)" .env

# Check Poetry environment
poetry env info

# List installed packages
poetry show

# Check Docker images
docker images | grep ai-gateway

# Check running containers
docker ps | grep ai-gateway

# Check build cache
docker builder du

# Docker Compose debugging
docker-compose ps
docker-compose logs -f
docker-compose exec app /bin/bash
```

## 📚 Additional Resources

- [Project README](../README.md) - General setup and configuration
- [Docker Images](docker-images.md) - Detailed Docker build information
- [Poetry Documentation](https://python-poetry.org/docs/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)