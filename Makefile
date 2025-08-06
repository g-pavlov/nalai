# Default target - show help
.DEFAULT_GOAL := help

# Environment variables
IMAGE_NAME ?= nalai
VERSION ?= latest

# Setup Commands
# ==============

.PHONY: setup-dev install validate-env

# Setup development environment
setup-dev:
	@echo "🔧 Setting up development environment..."
	@echo "Checking required tools..."
	
	# Check Python
	@python --version || (echo "❌ Python not found. Please install Python 3.12+" && exit 1)
	
	# Check/Install Poetry (hard dependency)
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "📦 Installing Poetry (hard dependency)..."; \
		./scripts/install_poetry.sh; \
	else \
		echo "✅ Poetry already installed: $$(poetry --version)"; \
	fi
	
	# Check Git
	@git --version || (echo "❌ Git not found. Please install Git" && exit 1)
	
	# Check Docker (optional but recommended)
	@if command -v docker >/dev/null 2>&1; then \
		echo "✅ Docker available: $$(docker --version)"; \
	else \
		echo "⚠️  Docker not found. Install for containerization features"; \
		echo "  Run: ./scripts/install_docker.sh"; \
	fi
	
	# Check Docker Compose
	@if command -v docker-compose >/dev/null 2>&1; then \
		echo "✅ Docker Compose available: $$(docker-compose --version)"; \
	else \
		echo "⚠️  Docker Compose not found. Install for docker-compose features"; \
	fi
	
	# Check/Install Trivy (for security scanning)
	@if command -v trivy >/dev/null 2>&1; then \
		echo "✅ Trivy available: $$(trivy --version | head -1)"; \
	else \
		echo "🔒 Installing Trivy for security scanning..."; \
		./scripts/install_trivy.sh; \
	fi
	
	# Install project dependencies
	@echo "📦 Installing project dependencies..."
	@poetry install --with=testing,dev
	
	# Install git hooks (version management)
	@echo "🔗 Installing git hooks..."
	@make install-git-hooks
	
	@echo "✅ Development environment ready!"
	@echo "Run 'make serve' to start the development server"

# Install dependencies
install:
	poetry install --with=testing,dev

# Validate environment (Python version, Poetry version, etc.)
validate-env:
	@echo "🔍 Validating environment..."
	@python --version | grep "3.12" || (echo "❌ Python 3.12 required" && exit 1)
	@poetry --version | grep "2.1" || (echo "❌ Poetry 2.1+ required" && exit 1)
	@echo "✅ Environment validation passed"

# Code Quality Commands
# ====================

.PHONY: lint lint-fix

# Run linting and formatting (CI-safe, no auto-fix)
lint: install
	@echo "🔧 Formatting code..."
	@poetry run ruff format src/ tests/
	@echo "🔍 Checking linting issues..."
	@poetry run ruff check src/ tests/
	@echo "✅ Code quality checks completed"

# Run linting and formatting with auto-fix (local development)
lint-fix: install
	@echo "🔧 Formatting code..."
	@poetry run ruff format src/ tests/
	@echo "🔍 Checking and fixing linting issues..."
	@poetry run ruff check --fix src/ tests/
	@echo "✅ Code quality checks completed"

# Testing Commands
# ===============

.PHONY: test test-integration test-coverage

# Run unit tests
test: install
	poetry run pytest tests/unit/ -v

# Run integration tests
test-integration: install
	poetry run pytest tests/integration/ -v

# Run all tests with coverage
test-coverage: install
	@echo "🧪 Running tests with coverage..."
	@time poetry run pytest tests/ -v --cov=src/api_assistant --cov-report=term-missing --cov-report=html --ignore=tests/unit/core/test_tool_node.py --ignore=tests/unit/tools/test_http_requests.py --ignore=tests/integration/test_chunk_accumulation.py
	@echo "✅ Tests completed"

# Security Commands
# ================

.PHONY: security security-image

# Run security scan (filesystem)
security: install
	@echo "🔒 Running security scan..."
	@trivy fs --format sarif --output trivy-results.sarif .
	@echo "✅ Security scan completed"

# Run security scan on Docker image
security-image: install
	@echo "🔒 Running security scan on Docker image..."
	@trivy image --format sarif --output trivy-results.sarif $(IMAGE_NAME):$(VERSION)
	@echo "✅ Docker image security scan completed"

# Docker Commands
# ==============

.PHONY: docker-build docker-run

# Build Docker image (development)
docker-build: install
	docker build -t $(IMAGE_NAME):latest .

# Build production Docker image
docker-build-prod: install
	docker build -t $(IMAGE_NAME):prod --target runtime .

# Run Docker container
docker-run: docker-build
	docker run -p 8080:8080 --env-file .env -v $(PWD)/data:/var/lib/nalai/data $(IMAGE_NAME):latest

# Run production Docker container
docker-run-prod: docker-build-prod
	docker run -p 8080:8080 --env-file .env -v $(PWD)/data:/var/lib/nalai/data $(IMAGE_NAME):prod

# Development Server Commands
# ==========================

.PHONY: serve

# Start development server
serve: install
	poetry run uvicorn api_assistant.server.app:app --host 0.0.0.0 --port 8000 --reload

# Build Commands
# Cleanup Commands
# ===============

.PHONY: clean

# Clean up
clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf .pytest_cache
	find . -name "*.pyc" -delete
	rm -rf dist

# CI/CD Commands
# =============

.PHONY: validate-deps check check-local ci-local test-gh-actions

# Validate dependency categorization
validate-deps: install
	@echo "📦 Validating dependencies..."
	@poetry run python scripts/lint_dependencies.py || (echo "❌ Dependency validation failed" && exit 1)
	@echo "✅ Dependency validation passed"

# Run all checks (CI-safe, no auto-fix)
check: lint test-coverage validate-deps security
	@echo "✅ All checks passed"

# Run all checks with auto-fix (local development)
check-local: lint-fix test-coverage validate-deps security
	@echo "✅ All checks passed"

# Simulate full CI pipeline locally
ci-local: check build docker-build-prod
	@echo "✅ Full CI pipeline simulation completed"

# Test GitHub Actions locally
test-gh-actions:
	@echo "🔧 Testing GitHub Actions locally..."
	@./scripts/test-github-actions.sh

# Build Commands
# =============

.PHONY: build

# Build development package
build: install
	@echo "📦 Building development package..."
	@poetry build
	@echo "✅ Build completed"

# Demo Commands
# ============

.PHONY: ui-run ui-stop

# Start API Assistant with UI demo
ui-run:
	@echo "🚀 Starting API Assistant with Custom UI (Demo)..."
	@echo "=============================================="
	@./scripts/check_env.sh
	@echo ""
	@echo "🐳 Starting services with Docker Compose..."
	@docker-compose up --build -d
	@echo ""
	@echo "✅ Demo is starting up!"
	@echo "🌐 UI will be available at: http://localhost:3001"
	@echo "🔧 API will be available at: http://localhost:8000"
	@echo ""
	@echo "📋 To stop the demo, run: make ui-stop"

# Stop all demo services
ui-stop:
	@echo "🛑 Stopping all demo services..."
	@docker-compose down
	@echo "✅ Demo services stopped"

# Tool Management Commands
# ======================

.PHONY: tool-info tool-versions update-tool-versions

# Show information about a specific tool
tool-info:
	@if [ -z "$(TOOL)" ]; then \
		echo "Usage: make tool-info TOOL=<tool_name>"; \
		echo "Available tools:"; \
		python3 scripts/install_config.py list-tools; \
	else \
		python3 scripts/install_config.py tool-info "$(TOOL)"; \
	fi

# Show versions of all tools
tool-versions:
	@echo "📋 Tool Version Information:"
	@echo ""
	@python3 scripts/install_config.py list-tools | while read tool; do \
		echo "=== $$tool ==="; \
		python3 scripts/install_config.py tool-info "$$tool"; \
		echo ""; \
	done

# Update tool versions in configuration
update-tool-versions:
	@echo "🔄 Updating tool versions in configuration..."
	@echo "This will check for latest versions and update install_config.yaml"
	@echo "Note: This is a development tool - review changes before committing"
	@python3 scripts/update_tool_versions.py

# Version Management Commands
# ==========================

.PHONY: version init-version bump-patch bump-minor bump-major install-git-hooks

# Get current version
version:
	@source scripts/version_utils_github.sh && get_or_create_version

# Initialize version (creates 0.1.0 if no tags exist)
init-version:
	@echo "Initializing version to 0.1.0..."
	@git tag 0.1.0
	@echo "Created initial version tag: 0.1.0"
	@echo "Push the tag with: git push origin 0.1.0"

# Bump patch version (bug fixes)
bump-patch:
	@source scripts/version_utils_github.sh && \
	CURRENT_VERSION=$$(get_or_create_version) && \
	NEW_VERSION=$$(increment_patch_version "$$CURRENT_VERSION") && \
	echo "Bumping patch version: $$CURRENT_VERSION → $$NEW_VERSION" && \
	git tag "$$NEW_VERSION" && \
	echo "Created tag: $$NEW_VERSION" && \
	echo "Push with: git push origin $$NEW_VERSION"

# Bump minor version (new features)
bump-minor:
	@source scripts/version_utils_github.sh && \
	CURRENT_VERSION=$$(get_or_create_version) && \
	NEW_VERSION=$$(increment_minor_version "$$CURRENT_VERSION") && \
	echo "Bumping minor version: $$CURRENT_VERSION → $$NEW_VERSION" && \
	git tag "$$NEW_VERSION" && \
	echo "Created tag: $$NEW_VERSION" && \
	echo "Push with: git push origin $$NEW_VERSION"

# Bump major version (breaking changes)
bump-major:
	@source scripts/version_utils_github.sh && \
	CURRENT_VERSION=$$(get_or_create_version) && \
	NEW_VERSION=$$(increment_major_version "$$CURRENT_VERSION") && \
	echo "Bumping major version: $$CURRENT_VERSION → $$NEW_VERSION" && \
	git tag "$$NEW_VERSION" && \
	echo "Created tag: $$NEW_VERSION" && \
	echo "Push with: git push origin $$NEW_VERSION"

# Install git hooks for automatic tag pushing and dependency validation
install-git-hooks:
	@echo "Installing git hooks for automatic tag pushing and dependency validation..."
	@mkdir -p .git/hooks
	
	# Pre-push hook for version tags
	@echo '#!/bin/bash' > .git/hooks/pre-push
	@echo '# Pre-push hook to automatically push version tags' >> .git/hooks/pre-push
	@echo '' >> .git/hooks/pre-push
	@echo '# Get all local version tags that are not on remote' >> .git/hooks/pre-push
	@echo 'local_tags=$$(git tag --list | grep -E "^[0-9]+\.[0-9]+\.[0-9]+$$" | while read tag; do' >> .git/hooks/pre-push
	@echo '    if ! git ls-remote --tags origin | grep -q "refs/tags/$$tag$$"; then' >> .git/hooks/pre-push
	@echo '        echo "$$tag"' >> .git/hooks/pre-push
	@echo '    fi' >> .git/hooks/pre-push
	@echo 'done)' >> .git/hooks/pre-push
	@echo '' >> .git/hooks/pre-push
	@echo '# If we have local version tags, push them' >> .git/hooks/pre-push
	@echo 'if [ -n "$$local_tags" ]; then' >> .git/hooks/pre-push
	@echo '    echo "Pushing version tags: $$local_tags"' >> .git/hooks/pre-push
	@echo '    git push origin $$local_tags' >> .git/hooks/pre-push
	@echo 'fi' >> .git/hooks/pre-push
	@chmod +x .git/hooks/pre-push
	
	# Pre-commit hook for code quality and dependency validation
	@echo '#!/bin/bash' > .git/hooks/pre-commit
	@echo '# Pre-commit hook to validate code quality and dependencies' >> .git/hooks/pre-commit
	@echo '' >> .git/hooks/pre-commit
	@echo '# Ensure dependencies are installed and lock file is up to date' >> .git/hooks/pre-commit
	@echo 'make install' >> .git/hooks/pre-commit
	@echo '' >> .git/hooks/pre-commit
	@echo '# Run code quality checks (format + lint)' >> .git/hooks/pre-commit
	@echo 'echo "🔧 Running code quality checks..."' >> .git/hooks/pre-commit
	@echo 'if ! make lint >/dev/null 2>&1; then' >> .git/hooks/pre-commit
	@echo '    echo "❌ Code quality issues found"' >> .git/hooks/pre-commit
	@echo '    echo "Run '\''make lint'\'' to see details"' >> .git/hooks/pre-commit
	@echo '    exit 1' >> .git/hooks/pre-commit
	@echo 'fi' >> .git/hooks/pre-commit
	@echo '' >> .git/hooks/pre-commit
	@echo '# Check dependency categorization' >> .git/hooks/pre-commit
	@echo 'echo "📦 Validating dependencies..."' >> .git/hooks/pre-commit
	@echo 'if ! poetry run python scripts/lint_dependencies.py >/dev/null 2>&1; then' >> .git/hooks/pre-commit
	@echo '    echo "❌ Dependency categorization issues found"' >> .git/hooks/pre-commit
	@echo '    echo "Run '\''make validate-deps'\'' to see details"' >> .git/hooks/pre-commit
	@echo '    exit 1' >> .git/hooks/pre-commit
	@echo 'fi' >> .git/hooks/pre-commit
	@echo '' >> .git/hooks/pre-commit
	@echo 'echo "✅ Pre-commit checks passed"' >> .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	
	@echo "Git hooks installed successfully!"
	@echo "Now when you run 'git push', version tags will be pushed automatically."
	@echo "When you commit, code quality and dependencies will be validated automatically."

# Help
# ====

.PHONY: help

help:
	@echo "\033[1m🔧 Setup:\033[0m"
	@echo "  make setup-dev           - Setup complete development environment"
	@echo "  make install             - Install dependencies"
	@echo "  make validate-env        - Validate environment (Python, Poetry versions)"
	@echo ""
	@echo "\033[1m💻 Development:\033[0m"
	@echo "  make lint                - Format code and run linting (CI-safe)"
	@echo "  make lint-fix            - Format code and run linting with auto-fix"
	@echo "  make serve               - Start development server"
	@echo "  make docker-build        - Build Docker image (development)"
	@echo "  make docker-run          - Run Docker container"
	@echo "  make ui-run              - Start API Assistant with UI demo"
	@echo "  make ui-stop             - Stop all demo services"
	@echo ""
	@echo "\033[1m🧪 Testing:\033[0m"
	@echo "  make test                - Run unit tests"
	@echo "  make test-integration    - Run integration tests"
	@echo "  make test-coverage       - Run all tests with coverage"
	@echo "  make security            - Run security scan (filesystem)"
	@echo "  make security-image      - Run security scan on Docker image"
	@echo "  make validate-deps       - Validate dependencies"
	@echo ""
	@echo "\033[1m📦 Build:\033[0m"
	@echo "  make build               - Build development package"
	@echo ""
	@echo "\033[1m📦 CI/CD:\033[0m"
	@echo "  make check               - Run all checks (CI-safe)"
	@echo "  make check-local         - Run all checks with auto-fix (local)"
	@echo "  make ci-local            - Simulate full CI pipeline locally"
	@echo "  make test-gh-actions     - Test GitHub Actions locally"
	@echo ""
	@echo "\033[1m🏷️  Release Version:\033[0m"
	@echo "  make version             - Show current version"
	@echo "  make init-version        - Initialize version to 0.1.0"
	@echo "  make bump-patch          - Bump patch version (bug fixes)"
	@echo "  make bump-minor          - Bump minor version (new features)"
	@echo "  make bump-major          - Bump major version (breaking changes)"
	@echo ""
	@echo "\033[1m🛠️  Utils:\033[0m"
	@echo "  make clean               - Clean up generated files"
	@echo "  make install-git-hooks   - Install git hooks for version tags and dependency validation"
	@echo ""
	@echo "\033[1m🔧 Tool Management:\033[0m"
	@echo "  make tool-info TOOL=<name> - Show information about a specific tool"
	@echo "  make tool-versions        - Show versions of all tools"
	@echo "  make update-tool-versions - Update tool versions in configuration"
