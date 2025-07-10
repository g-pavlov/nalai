#!/bin/bash

# BATS Test Runner for CI Pipeline Scripts
# ========================================
# This script runs BATS tests for shell scripts

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if BATS is installed
if ! command -v bats >/dev/null 2>&1; then
    print_error "BATS is not installed. Please run setup-bats.sh first."
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

print_status "Running BATS tests for CI pipeline scripts..."
echo "=================================================="
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Run BATS tests
print_status "Running test-pipeline-bats.bats (main pipeline suite)..."
bats "$SCRIPT_DIR/test-pipeline-bats.bats"

print_status "Running test-version-management.bats (version management suite)..."
bats "$SCRIPT_DIR/test-version-management.bats"

print_success "All BATS tests (including version management) passed! 🎉"
exit 0
