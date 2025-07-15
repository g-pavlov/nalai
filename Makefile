# Default target - show help
.DEFAULT_GOAL := help

# Setup Commands
# ==============

.PHONY: setup-dev install

# Setup development environment
setup-dev:
	@echo "🔧 Setting up development environment..."
	@echo "Checking required tools..."
	
	# Check Python
	@python --version || (echo "❌ Python not found. Please install Python 3.12+" && exit 1)
	
	# Check/Install Poetry
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "📦 Installing Poetry..."; \
		pip install poetry; \
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
	fi
	
	# Check Docker Compose
	@if command -v docker-compose >/dev/null 2>&1; then \
		echo "✅ Docker Compose available: $$(docker-compose --version)"; \
	else \
		echo "⚠️  Docker Compose not found. Install for docker-compose features"; \
	fi
	
	# Install project dependencies
	@echo "📦 Installing project dependencies..."
	@poetry install --with=testing
	
	# Install git hooks (version management)
	@echo "🔗 Installing git hooks..."
	@make install-version-hooks
	
	@echo "✅ Development environment ready!"
	@echo "Run 'make serve' to start the development server"

# Install dependencies
install:
	poetry install --with=testing

# Code Quality Commands
# ====================

.PHONY: lint format

# Run linting
lint:
	poetry run ruff check src/ tests/

# Format code
format:
	poetry run ruff format src/ tests/

# Testing Commands
# ===============

.PHONY: test test-integration test-coverage

# Run unit tests
test:
	poetry run pytest tests/unit/ -v

# Run integration tests
test-integration:
	poetry run pytest tests/integration/ -v

# Run all tests with coverage
test-coverage:
	poetry run pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

# Security Commands
# ================

.PHONY: ci-security

# Run security scan locally
ci-security:
	trivy fs --format sarif --output trivy-results.sarif .

# Docker Commands
# ==============

.PHONY: docker-build docker-run

# Build Docker image
docker-build:
	docker build -t api-assistant:latest .

# Run Docker container
docker-run:
	docker run -p 8080:8080 api-assistant:latest

# Development Server Commands
# ==========================

.PHONY: serve serve-prod

# Start development server
serve:
	poetry run uvicorn api_assistant.server.app:app --host 0.0.0.0 --port 8000 --reload

# Start production-like server
serve-prod:
	poetry run uvicorn api_assistant.server.app:app --host 0.0.0.0 --port 8000 --no-reload --log-config logging.yaml

# Build Commands
# =============

.PHONY: build build-prod

# Build development package
build:
	poetry build

# Build production package
build-prod:
	poetry build --format wheel

# Cleanup Commands
# ===============

.PHONY: clean

# Clean up
clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf .pytest_cache
	find . -name "*.pyc" -delete

# CI/CD Commands
# =============

.PHONY: ci-test ci-lint ci-deps

# Run CI tests locally
ci-test:
	poetry install --with=testing
	poetry run pytest tests/ -v --cov=src --cov-report=xml

# Run CI linting locally
ci-lint:
	poetry install --with=testing
	poetry run ruff check src/ tests/
	poetry run ruff format --check src/ tests/

# Run dependency linting
ci-deps:
	poetry run python scripts/lint_dependencies.py

# Version Management Commands
# ==========================

.PHONY: version init-version bump-patch bump-minor bump-major install-version-hooks

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

# Install git hooks for automatic tag pushing
install-version-hooks:
	@echo "Installing git hooks for automatic tag pushing..."
	@mkdir -p .git/hooks
	@cat > .git/hooks/pre-push << 'EOF'
	#!/bin/bash
	# Pre-push hook to automatically push version tags

	# Get the current branch
	current_branch=$(git symbolic-ref HEAD | sed 's!refs/heads/!!')

	# Get all local version tags that aren't on remote
	local_tags=$(git tag --list | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | while read tag; do
	    if ! git ls-remote --tags origin | grep -q "refs/tags/$tag$"; then
	        echo "$tag"
	    fi
	done)

	# If we have local version tags, push them
	if [ -n "$local_tags" ]; then
	    echo "Pushing version tags: $local_tags"
	    git push origin $local_tags
	fi
	EOF
	@chmod +x .git/hooks/pre-push
	@echo "Git hooks installed successfully!"
	@echo "Now when you run 'git push', version tags will be pushed automatically."

# Help
# ====

.PHONY: help

help:
	@echo "\033[1m🔧 Setup Commands:\033[0m"
	@echo "  make setup-dev           - Setup complete development environment"
	@echo "  make install             - Install dependencies"
	@echo ""
	@echo "\033[1m📝 Code Quality Commands:\033[0m"
	@echo "  make lint                - Run linting"
	@echo "  make format              - Format code"
	@echo ""
	@echo "\033[1m🧪 Testing Commands:\033[0m"
	@echo "  make test                - Run unit tests"
	@echo "  make test-integration    - Run integration tests"
	@echo "  make test-coverage       - Run all tests with coverage"
	@echo ""
	@echo "\033[1m🔒 Security Commands:\033[0m"
	@echo "  make ci-security         - Run security scan locally"
	@echo ""
	@echo "\033[1m🐳 Docker Commands:\033[0m"
	@echo "  make docker-build         - Build Docker image"
	@echo "  make docker-run           - Run Docker container"
	@echo ""
	@echo "\033[1m🚀 Development Server Commands:\033[0m"
	@echo "  make serve               - Start development server"
	@echo "  make serve-prod          - Start production-like server"
	@echo ""
	@echo "\033[1m📦 Build Commands:\033[0m"
	@echo "  make build               - Build development package"
	@echo "  make build-prod          - Build production package"
	@echo ""
	@echo "\033[1m🧹 Cleanup Commands:\033[0m"
	@echo "  make clean               - Clean up generated files"
	@echo ""
	@echo "\033[1m🚦 CI/CD Commands:\033[0m"
	@echo "  make ci-test             - Run CI tests locally"
	@echo "  make ci-lint             - Run CI linting locally"
	@echo "  make ci-deps             - Run dependency linting"
	@echo ""
	@echo "\033[1m🏷️  Version Management Commands:\033[0m"
	@echo "  make version             - Show current version"
	@echo "  make init-version        - Initialize version to 0.1.0"
	@echo "  make bump-patch          - Bump patch version (bug fixes)"
	@echo "  make bump-minor          - Bump minor version (new features)"
	@echo "  make bump-major          - Bump major version (breaking changes)"
	@echo "  make install-version-hooks - Install git hooks for auto tag pushing"
