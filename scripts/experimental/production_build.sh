#!/bin/bash

# Production Build Script - handles all internal build steps
# This script is designed to run inside Docker containers

set -e

echo "🏭 Starting complete production build process..."

# Check if running in Docker (safety check for cleanup)
if [ ! -f /.dockerenv ]; then
    echo "❌ ERROR: This script should only run inside Docker containers!"
    echo "   Use 'make build-prod' for local builds instead."
    exit 1
fi

echo "✅ Detected Docker environment, proceeding..."

# Step 1: Generate production configurations
echo "🚀 Production configurations not needed for simplified build..."
echo "✅ Skipping production config generation"

# Step 2: Build wheels
echo "🛞 Building wheels for all packages..."
poetry run python scripts/build_wheels.py
echo "✅ Wheels built successfully"

# Step 3: Install production dependencies
echo "📦 Step 3: Installing production dependencies..."
poetry install --no-interaction --no-ansi --only=main
echo "✅ Dependencies installed"

# Step 4: Export clean requirements.txt (excluding local packages)
echo "📦 Exporting clean requirements.txt..."
poetry run python scripts/experimental/generate_clean_requirements.py

# Step 5: Clean up build artifacts
echo "🧹 Step 5: Cleaning up build artifacts..."
# Remove CI/CD tools and scripts
rm -rf scripts/
# Remove source packages (already built into wheels)
rm -rf packages/
# Remove wheel artifacts (already installed)
rm -rf wheels/
# Remove production config files
rm -f pyproject_prod.toml
find . -name "*_prod.toml" -delete 2>/dev/null || true
# Remove build dependencies (suppress errors if not installed)
pip uninstall -y tomlkit || echo "tomlkit not installed, skipping"
# Clean Poetry cache and temporary files
poetry cache clear --all . || echo "Poetry cache clear skipped"
# Remove cache directories
rm -rf ~/.cache/pip || true
rm -rf ~/.cache/poetry || true
# Clean temporary files
find /tmp -name "tmp*" -delete 2>/dev/null || true
echo "✅ Build artifacts cleaned"

echo "🎉 Complete production build finished successfully!" 