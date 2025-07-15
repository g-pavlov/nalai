#!/bin/bash

# GitHub Actions Local Testing Script
# This script helps test GitHub Actions workflows locally

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Check if required tools are installed
check_requirements() {
    print_status "Checking requirements..."
    
    # Source the base installation functions
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$SCRIPT_DIR/install_base.sh"
    
    # Check and install GitHub CLI if needed (on-demand)
    if ! command -v gh >/dev/null 2>&1; then
        print_warning "GitHub CLI (gh) is not installed"
        echo "Installing GitHub CLI on demand..."
        source "$SCRIPT_DIR/install_gh.sh"
    else
        print_success "GitHub CLI already installed: $(gh --version | head -1)"
    fi
    
    # Check and install act if needed (on-demand)
    if ! command -v act >/dev/null 2>&1; then
        print_warning "act is not installed - will only use gh CLI"
        echo "Installing act on demand..."
        source "$SCRIPT_DIR/install_act.sh"
    else
        print_success "act already installed: $(act --version)"
    fi
    
    # Check Docker for act (optional, but recommended)
    if ! command -v docker >/dev/null 2>&1; then
        print_warning "Docker is not installed - act will not work"
        echo "Docker is optional but recommended for full workflow testing"
        echo "Install Docker for full local testing capabilities:"
        echo "  https://docs.docker.com/get-docker/"
    else
        print_success "Docker available: $(docker --version)"
    fi
    
    print_success "Requirements check completed"
}

# List available workflows
list_workflows() {
    print_status "Available workflows:"
    echo "1. pr-check.yml - Pull Request Checks"
    echo "2. feature-branch.yml - Feature Branch Pipeline"
    echo "3. release-pipeline.yml - Release Pipeline"
    echo ""
}

# Test with GitHub CLI
test_with_gh() {
    print_status "Testing with GitHub CLI..."
    
    # Check if we're authenticated
    if ! gh auth status >/dev/null 2>&1; then
        print_warning "Not authenticated with GitHub CLI"
        echo "Authentication is optional for local testing."
        echo "To monitor real workflow runs, run: gh auth login"
        echo ""
        print_status "Available gh commands (when authenticated):"
        echo "  gh run list                    - List recent workflow runs"
        echo "  gh run list --workflow=pr-check.yml - List runs for specific workflow"
        echo "  gh run watch                   - Watch the latest run"
        echo "  gh run watch <run-id>          - Watch a specific run"
        echo "  gh run download                - Download artifacts from latest run"
        echo "  gh run rerun                   - Re-run the latest failed workflow"
        echo "  gh run rerun <run-id>          - Re-run a specific workflow"
        echo "  gh run rerun --debug           - Re-run with debug logging"
        echo ""
        print_status "For local testing without authentication, use:"
        echo "  make ci-local                  - Full CI pipeline simulation"
        echo "  act -l                         - List available workflows (if Docker available)"
    else
        # List recent runs
        print_status "Recent workflow runs:"
        gh run list --limit 5
        
        echo ""
        print_status "Available gh commands:"
        echo "  gh run list                    - List recent workflow runs"
        echo "  gh run list --workflow=pr-check.yml - List runs for specific workflow"
        echo "  gh run watch                   - Watch the latest run"
        echo "  gh run watch <run-id>          - Watch a specific run"
        echo "  gh run download                - Download artifacts from latest run"
        echo "  gh run rerun                   - Re-run the latest failed workflow"
        echo "  gh run rerun <run-id>          - Re-run a specific workflow"
        echo "  gh run rerun --debug           - Re-run with debug logging"
    fi
}

# Test with act (if available)
test_with_act() {
    if ! command -v act >/dev/null 2>&1; then
        print_warning "act not available - skipping act tests"
        return
    fi
    
    if ! command -v docker >/dev/null 2>&1; then
        print_warning "Docker not available - act requires Docker"
        return
    fi
    
    print_status "Testing with act..."
    
    # List available workflows
    print_status "Available workflows in act:"
    act -l
    
    echo ""
    print_status "Available act commands:"
    echo "  act -l                         - List available workflows"
    echo "  act pull_request               - Run PR check workflow"
    echo "  act push                       - Run feature branch workflow"
    echo "  act -n                         - Dry run (see what would happen)"
    echo "  act --list                     - List all workflows"
    echo "  act --verbose                  - Verbose output"
    echo "  act --secret GITHUB_TOKEN=dummy - Set secrets"
    echo "  act --env-file .env            - Use environment file"
}

# Simulate CI locally using Makefile
test_with_make() {
    print_status "Testing with Makefile (simulates CI locally)..."
    
    echo ""
    print_status "Available make commands for CI simulation:"
    echo "  make ci-local                  - Full CI pipeline simulation"
    echo "  make check                     - All checks (CI-safe)"
    echo "  make check-local               - All checks with auto-fix"
    echo "  make lint                      - Linting (CI-safe)"
    echo "  make lint-fix                  - Linting with auto-fix"
    echo "  make test-coverage             - Tests with coverage"
    echo "  make security                  - Security scan"
    echo "  make validate-deps             - Dependency validation"
    echo ""
    
    read -p "Run full CI simulation? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Running full CI simulation..."
        make ci-local
        print_success "CI simulation completed"
    fi
}

# Main function
main() {
    echo "🔧 GitHub Actions Local Testing Tool"
    echo "===================================="
    echo ""
    
    check_requirements
    echo ""
    
    list_workflows
    echo ""
    
    # Test with different tools
    test_with_gh
    echo ""
    
    test_with_act
    echo ""
    
    test_with_make
    echo ""
    
    print_success "Local testing setup complete!"
    echo ""
    echo "💡 Tips:"
    echo "  - Use 'make ci-local' for quick CI simulation (no auth required)"
    echo "  - Use 'act' for full workflow testing (requires Docker, no auth required)"
    echo "  - Use 'gh auth login' then 'gh run watch' to monitor real workflow runs"
    echo "  - Use 'gh run rerun' to re-run failed workflows (requires auth)"
}

# Run main function
main "$@" 