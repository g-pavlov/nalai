#!/bin/bash

# Base installation script with platform-independent functions
# This script provides common functions for tool installation across platforms

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

# Detect operating system
detect_os() {
    case "$OSTYPE" in
        darwin*)
            echo "macos"
            ;;
        linux-gnu*|linux*)
            echo "linux"
            ;;
        msys*|cygwin*|win32*)
            echo "windows"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Detect package manager
detect_package_manager() {
    local os="$1"
    
    case "$os" in
        macos)
            if command -v brew >/dev/null 2>&1; then
                echo "brew"
            else
                echo "none"
            fi
            ;;
        linux)
            if command -v apt-get >/dev/null 2>&1; then
                echo "apt"
            elif command -v yum >/dev/null 2>&1; then
                echo "yum"
            elif command -v dnf >/dev/null 2>&1; then
                echo "dnf"
            elif command -v pacman >/dev/null 2>&1; then
                echo "pacman"
            elif command -v zypper >/dev/null 2>&1; then
                echo "zypper"
            else
                echo "none"
            fi
            ;;
        windows)
            if command -v winget >/dev/null 2>&1; then
                echo "winget"
            elif command -v choco >/dev/null 2>&1; then
                echo "choco"
            elif command -v scoop >/dev/null 2>&1; then
                echo "scoop"
            else
                echo "none"
            fi
            ;;
        *)
            echo "none"
            ;;
    esac
}

# Install package using detected package manager
install_package() {
    local package="$1"
    local os="$2"
    local pkg_manager="$3"
    
    case "$pkg_manager" in
        brew)
            print_status "Installing $package with Homebrew..."
            brew install "$package"
            ;;
        apt)
            print_status "Installing $package with apt..."
            sudo apt-get update
            sudo apt-get install -y "$package"
            ;;
        yum)
            print_status "Installing $package with yum..."
            sudo yum install -y "$package"
            ;;
        dnf)
            print_status "Installing $package with dnf..."
            sudo dnf install -y "$package"
            ;;
        pacman)
            print_status "Installing $package with pacman..."
            sudo pacman -S --noconfirm "$package"
            ;;
        zypper)
            print_status "Installing $package with zypper..."
            sudo zypper install -y "$package"
            ;;
        winget)
            print_status "Installing $package with winget..."
            winget install "$package"
            ;;
        choco)
            print_status "Installing $package with Chocolatey..."
            choco install "$package" -y
            ;;
        scoop)
            print_status "Installing $package with Scoop..."
            scoop install "$package"
            ;;
        none)
            print_error "No supported package manager found for $os"
            print_manual_install_instructions "$package" "$os"
            return 1
            ;;
        *)
            print_error "Unknown package manager: $pkg_manager"
            return 1
            ;;
    esac
}

# Print manual installation instructions
print_manual_install_instructions() {
    local package="$1"
    local os="$2"
    
    print_warning "Please install $package manually for your system:"
    case "$package" in
        gh)
            echo "  https://cli.github.com/"
            ;;
        act)
            echo "  https://github.com/nektos/act"
            ;;
        poetry)
            echo "  https://python-poetry.org/docs/#installation"
            ;;
        docker)
            echo "  https://docs.docker.com/get-docker/"
            ;;
        trivy)
            echo "  https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
            ;;
        *)
            echo "  Please search for installation instructions for $package on $os"
            ;;
    esac
}

# Check if tool is installed
is_tool_installed() {
    local tool="$1"
    command -v "$tool" >/dev/null 2>&1
}

# Main installation function
install_tool() {
    local tool="$1"
    local package_name="$2"
    
    # Check if tool is already installed and compatible
    if is_tool_installed "$tool"; then
        local current_version=$($tool --version 2>/dev/null | head -1 || echo "version unknown")
        
        # Check version compatibility using Python config manager
        if command -v python3 >/dev/null 2>&1; then
            local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
            local config_script="$script_dir/install_config.py"
            
            if [ -f "$config_script" ]; then
                local is_compatible=$(python3 "$config_script" check-compatibility "$tool")
                if [ "$is_compatible" = "Compatible" ]; then
                    print_success "$tool already installed and compatible: $current_version"
                    return 0
                else
                    print_warning "$tool installed but version may be incompatible: $current_version"
                    # Continue with installation to get compatible version
                fi
            else
                print_success "$tool already installed: $current_version"
                return 0
            fi
        else
            print_success "$tool already installed: $current_version"
            return 0
        fi
    fi
    
    print_status "Installing $tool..."
    
    local os=$(detect_os)
    local pkg_manager=$(detect_package_manager "$os")
    
    if [ "$pkg_manager" = "none" ]; then
        print_error "No supported package manager found for $os"
        print_manual_install_instructions "$tool" "$os"
        return 1
    fi
    
    if install_package "$package_name" "$os" "$pkg_manager"; then
        print_success "$tool installed successfully"
        return 0
    else
        print_error "Failed to install $tool"
        return 1
    fi
}

# Export functions for use in other scripts
export -f print_status print_success print_warning print_error
export -f detect_os detect_package_manager install_package
export -f print_manual_install_instructions is_tool_installed install_tool 