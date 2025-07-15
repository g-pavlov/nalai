#!/bin/bash
set -e

echo "🚀 Setting up GitHub Actions local testing tools..."

# Function to install gh CLI
install_gh() {
    echo "📦 Installing GitHub CLI (gh)..."
    
    if command -v gh >/dev/null 2>&1; then
        echo "✅ GitHub CLI already installed: $(gh --version)"
        return 0
    fi
    
    # Detect OS and install
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew >/dev/null 2>&1; then
            brew install gh
        else
            echo "❌ Homebrew not found. Please install Homebrew first:"
            echo "   https://brew.sh/"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get >/dev/null 2>&1; then
            # Ubuntu/Debian
            curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
            sudo apt-get update
            sudo apt-get install gh
        elif command -v yum >/dev/null 2>&1; then
            # RHEL/CentOS
            sudo yum install gh
        elif command -v dnf >/dev/null 2>&1; then
            # Fedora
            sudo dnf install gh
        else
            echo "❌ Unsupported Linux distribution. Please install gh manually:"
            echo "   https://github.com/cli/cli#installation"
            exit 1
        fi
    else
        echo "❌ Unsupported OS: $OSTYPE"
        echo "   Please install gh manually: https://github.com/cli/cli#installation"
        exit 1
    fi
    
    echo "✅ GitHub CLI installed: $(gh --version)"
}

# Function to install act
install_act() {
    echo "📦 Installing act (GitHub Actions local runner)..."
    
    if command -v act >/dev/null 2>&1; then
        echo "✅ act already installed: $(act --version)"
        return 0
    fi
    
    # Detect OS and install
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew >/dev/null 2>&1; then
            brew install act
        else
            echo "❌ Homebrew not found. Please install Homebrew first:"
            echo "   https://brew.sh/"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
    else
        echo "❌ Unsupported OS: $OSTYPE"
        echo "   Please install act manually: https://nektosact.com/installation/"
        exit 1
    fi
    
    echo "✅ act installed: $(act --version)"
}

# Function to check Docker
check_docker() {
    echo "🐳 Checking Docker..."
    
    if ! command -v docker >/dev/null 2>&1; then
        echo "❌ Docker not found. Please install Docker first:"
        echo "   https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        echo "❌ Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    echo "✅ Docker is running: $(docker --version)"
}

# Function to test GitHub CLI
test_gh() {
    echo "🔍 Testing GitHub CLI..."
    
    if ! gh auth status >/dev/null 2>&1; then
        echo "⚠️  GitHub CLI not authenticated. Please run:"
        echo "   gh auth login"
        echo ""
        echo "This will allow you to monitor GitHub Actions runs."
    else
        echo "✅ GitHub CLI authenticated"
        echo "   Current user: $(gh api user --jq .login)"
    fi
}

# Function to test act
test_act() {
    echo "🔍 Testing act..."
    
    if [ -d ".github/workflows" ]; then
        echo "📋 Available workflows:"
        act -l
        echo ""
        echo "✅ act is ready to test workflows locally"
        echo ""
        echo "Example usage:"
        echo "  act pull_request    # Test PR workflow"
        echo "  act push           # Test push workflow"
        echo "  act -n             # Dry run (see what would happen)"
    else
        echo "⚠️  No .github/workflows directory found"
        echo "   Create workflow files to test with act"
    fi
}

# Main execution
main() {
    echo "🔧 Setting up GitHub Actions local testing environment..."
    echo ""
    
    # Install tools
    install_gh
    install_act
    check_docker
    
    echo ""
    echo "🧪 Testing tools..."
    test_gh
    test_act
    
    echo ""
    echo "✅ GitHub Actions local testing setup complete!"
    echo ""
    echo "📚 Next steps:"
    echo "  1. Authenticate with GitHub: gh auth login"
    echo "  2. Test workflows locally: act pull_request"
    echo "  3. Monitor real runs: gh run watch"
    echo ""
    echo "📖 For more information, see: docs/github-actions-testing.md"
}

# Run main function
main "$@" 