# Default target - show help
.DEFAULT_GOAL := help

# Version Management Commands
# ===========================

.PHONY: help version init-version bump-patch bump-minor bump-major install-version-hooks

# Get current version
version:
	@source .ci/version_utils_github.sh && get_or_create_version

# Initialize version (creates 0.1.0 if no tags exist)
init-version:
	@echo "Initializing version to 0.1.0..."
	@git tag 0.1.0
	@echo "Created initial version tag: 0.1.0"
	@echo "Push the tag with: git push origin 0.1.0"

# Bump patch version (bug fixes)
bump-patch:
	@source .ci/version_utils_github.sh && \
	CURRENT_VERSION=$$(get_or_create_version) && \
	NEW_VERSION=$$(increment_patch_version "$$CURRENT_VERSION") && \
	echo "Bumping patch version: $$CURRENT_VERSION → $$NEW_VERSION" && \
	git tag "$$NEW_VERSION" && \
	echo "Created tag: $$NEW_VERSION" && \
	echo "Push with: git push origin $$NEW_VERSION"

# Bump minor version (new features)
bump-minor:
	@source .ci/version_utils_github.sh && \
	CURRENT_VERSION=$$(get_or_create_version) && \
	NEW_VERSION=$$(increment_minor_version "$$CURRENT_VERSION") && \
	echo "Bumping minor version: $$CURRENT_VERSION → $$NEW_VERSION" && \
	git tag "$$NEW_VERSION" && \
	echo "Created tag: $$NEW_VERSION" && \
	echo "Push with: git push origin $$NEW_VERSION"

# Bump major version (breaking changes)
bump-major:
	@source .ci/version_utils_github.sh && \
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

# Development Commands
# ===================

.PHONY: install test lint format clean serve

# Install dependencies
install:
	poetry install --with=testing

# Run tests
test:
	poetry run pytest tests/ -v

# Run linting
lint:
	poetry run ruff check src/ tests/

# Format code
format:
	poetry run ruff format src/ tests/

# Clean up
clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf .pytest_cache
	find . -name "*.pyc" -delete

# Test cache functionality
test-cache-mocked:
	poetry run python tests/integration/test_cache_with_mocked_llm.py

test-cache-integration:
	poetry run python tests/integration/test_cache_integration.py

# Start development server
serve:
	poetry run uvicorn api_assistant.server.app:app --host 0.0.0.0 --port 8000 --reload

# Docker Commands
# ==============

.PHONY: docker-build docker-test docker-run

# Build Docker image
docker-build:
	docker build -t api-assistant:latest .

# Test Docker image
docker-test:
	docker run --rm api-assistant:latest --help

# Run Docker container
docker-run:
	docker run -p 8080:8080 api-assistant:latest

# CI/CD Commands
# =============

.PHONY: ci-test ci-lint ci-security

# Run CI tests locally
ci-test:
	poetry install --with=testing
	poetry run pytest tests/ -v --cov=src --cov-report=xml

# Run CI linting locally
ci-lint:
	poetry install --with=testing
	poetry run ruff check src/ tests/
	poetry run ruff format --check src/ tests/

# Run security scan locally
ci-security:
	trivy fs --format sarif --output trivy-results.sarif .

# Help
# ====

.PHONY: help

help:
	@echo "\033[1m🏷️  Version Management Commands:\033[0m"
	@echo "  make version              - Show current version"
	@echo "  make init-version         - Initialize version to 0.1.0"
	@echo "  make bump-patch           - Bump patch version (bug fixes)"
	@echo "  make bump-minor           - Bump minor version (new features)"
	@echo "  make bump-major           - Bump major version (breaking changes)"
	@echo "  make install-version-hooks - Install git hooks for auto tag pushing"
	@echo ""
	@echo "\033[1m🛠️  Development Commands:\033[0m"
	@echo "  make install              - Install dependencies"
	@echo "  make test                 - Run tests"
	@echo "  make lint                 - Run linting"
	@echo "  make format               - Format code"
	@echo "  make clean                - Clean up generated files"
	@echo "  make serve                - Start development server"
	@echo ""
	@echo "\033[1m🐳  Docker Commands:\033[0m"
	@echo "  make docker-build         - Build Docker image"
	@echo "  make docker-test          - Test Docker image"
	@echo "  make docker-run           - Run Docker container"
	@echo ""
	@echo "\033[1m🚦  CI/CD Commands:\033[0m"
	@echo "  make ci-test              - Run CI tests locally"
	@echo "  make ci-lint              - Run CI linting locally"
	@echo "  make ci-security          - Run security scan locally"
