#!/bin/bash

# BATS Setup Script for Shell Script Testing
# ==========================================
# This script sets up BATS (Bash Automated Testing System) for improved shell script testing

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

# Function to check if BATS is installed
check_bats_installation() {
    if command -v bats >/dev/null 2>&1; then
        BATS_VERSION=$(bats --version 2>/dev/null || echo "unknown")
        print_success "BATS is already installed (version: $BATS_VERSION)"
        return 0
    else
        print_warning "BATS is not installed"
        return 1
    fi
}

# Function to install BATS on macOS
install_bats_macos() {
    print_status "Installing BATS on macOS..."
    
    if command -v brew >/dev/null 2>&1; then
        brew install bats-core/bats-core/bats-core
        print_success "BATS installed via Homebrew"
    else
        print_error "Homebrew not found. Please install Homebrew first:"
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        return 1
    fi
}

# Function to install BATS on Linux
install_bats_linux() {
    print_status "Installing BATS on Linux..."
    
    # Try different package managers
    if command -v apt-get >/dev/null 2>&1; then
        # Ubuntu/Debian
        sudo apt-get update
        sudo apt-get install -y bats
        print_success "BATS installed via apt-get"
    elif command -v yum >/dev/null 2>&1; then
        # CentOS/RHEL
        sudo yum install -y bats
        print_success "BATS installed via yum"
    elif command -v dnf >/dev/null 2>&1; then
        # Fedora
        sudo dnf install -y bats
        print_success "BATS installed via dnf"
    else
        print_error "No supported package manager found. Installing from source..."
        install_bats_from_source
    fi
}

# Function to install BATS from source
install_bats_from_source() {
    print_status "Installing BATS from source..."
    
    # Create temporary directory
    local tmpdir=$(mktemp -d)
    cd "$tmpdir"
    
    # Clone BATS repository
    git clone https://github.com/bats-core/bats-core.git
    cd bats-core
    
    # Install
    sudo ./install.sh /usr/local
    print_success "BATS installed from source"
    
    # Cleanup
    cd /
    rm -rf "$tmpdir"
}

# Function to install BATS
install_bats() {
    local os=$(uname -s)
    
    case "$os" in
        Darwin)
            install_bats_macos
            ;;
        Linux)
            install_bats_linux
            ;;
        *)
            print_error "Unsupported operating system: $os"
            print_status "Please install BATS manually: https://github.com/bats-core/bats-core"
            return 1
            ;;
    esac
}

# Function to create test configuration
setup_test_config() {
    print_status "Setting up test configuration..."
    
    # Create .batsrc if it doesn't exist
    if [ ! -f ".batsrc" ]; then
        cat > .batsrc <<'EOF'
# BATS Configuration File
# =======================

# Enable parallel execution (if supported)
# BATS_PARALLEL_JOBS=4

# Set timeout for tests (in seconds)
BATS_TIMEOUT=30

# Enable verbose output
BATS_VERBOSE=1

# Set test directory
BATS_TEST_DIRNAME=".ci/test"

# Additional BATS options
BATS_OPTS="--print-output-on-failure --show-output-of-passing-tests"
EOF
        print_success "Created .batsrc configuration file"
    else
        print_status ".batsrc already exists"
    fi
}

# Function to create test runner script
create_test_runner() {
    print_status "Creating test runner script..."
    
    cat > .ci/test/run-bats-tests.sh <<'EOF'
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
if bats "$SCRIPT_DIR/test-pipeline-bats.bats"; then
    print_success "All BATS tests passed! 🎉"
    exit 0
else
    print_error "Some BATS tests failed. Please review the output above."
    exit 1
fi
EOF

    chmod +x .ci/test/run-bats-tests.sh
    print_success "Created BATS test runner script"
}

# Function to create Makefile targets
add_makefile_targets() {
    print_status "Adding BATS test targets to Makefile..."
    
    # Check if targets already exist
    if grep -q "test-shell" Makefile; then
        print_status "BATS test targets already exist in Makefile"
        return 0
    fi
    
    # Add targets to Makefile
    cat >> Makefile <<'EOF'

## 🧪 Shell Script Testing (BATS)
test-shell:
	@echo "🧪 Running BATS tests for shell scripts..."
	@if command -v bats >/dev/null 2>&1; then \
		.ci/test/run-bats-tests.sh; \
	else \
		echo "❌ BATS not installed. Run 'make setup-bats' first."; \
		exit 1; \
	fi

setup-bats:
	@echo "🔧 Setting up BATS testing framework..."
	@.ci/test/setup-bats.sh

test-all: test test-shell
	@echo "✅ All tests completed (Python + Shell)"

.PHONY: test-shell setup-bats test-all
EOF

    print_success "Added BATS test targets to Makefile"
}

# Function to demonstrate BATS vs current approach
demonstrate_comparison() {
    print_status "Demonstrating BATS vs current testing approach..."
    echo ""
    echo "Current Approach vs BATS Comparison:"
    echo "===================================="
    echo ""
    echo "Current Approach:"
    echo "  ✅ Custom test framework with good coverage"
    echo "  ❌ Manual test organization and reporting"
    echo "  ❌ No built-in assertions or test isolation"
    echo "  ❌ Difficult to run individual tests"
    echo "  ❌ Limited error reporting"
    echo ""
    echo "BATS Approach:"
    echo "  ✅ Standard testing framework with wide adoption"
    echo "  ✅ Built-in assertions and test isolation"
    echo "  ✅ Individual test execution and reporting"
    echo "  ✅ Better error messages and debugging"
    echo "  ✅ Parallel test execution support"
    echo "  ✅ Integration with CI/CD tools"
    echo ""
    echo "Benefits of BATS:"
    echo "  • Better test organization with @test annotations"
    echo "  • Automatic setup/teardown with setup()/teardown()"
    echo "  • Rich assertion library ([, [[, assert, etc.)"
    echo "  • Better error reporting and debugging"
    echo "  • Integration with CI/CD pipelines"
    echo "  • Community support and documentation"
    echo ""
}

# Main function
main() {
    print_status "Setting up BATS for shell script testing..."
    echo "================================================="
    echo ""
    
    # Check if BATS is already installed
    if check_bats_installation; then
        print_status "BATS is already installed. Setting up configuration..."
    else
        print_status "Installing BATS..."
        install_bats
        
        # Verify installation
        if ! check_bats_installation; then
            print_error "BATS installation failed"
            exit 1
        fi
    fi
    
    # Setup test configuration
    setup_test_config
    
    # Create test runner
    create_test_runner
    
    # Add Makefile targets
    add_makefile_targets
    
    # Demonstrate comparison
    demonstrate_comparison
    
    echo "================================================="
    print_success "BATS setup completed!"
    echo ""
    print_status "Next steps:"
    echo "  1. Run BATS tests: make test-shell"
    echo "  2. Run all tests: make test-all"
    echo "  3. Run individual tests: bats .ci/test/test-pipeline-bats.bats"
    echo "  4. View BATS documentation: https://github.com/bats-core/bats-core"
    echo ""
    print_status "Example BATS test execution:"
    echo "  bats .ci/test/test-pipeline-bats.bats"
    echo ""
}

# Run main function
main "$@" 