#!/bin/bash

# Poetry installation script
# This script installs Poetry (Python package manager) on demand across all platforms

set -e

# Source the base installation functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/install_base.sh"

# Special installation for Poetry on different platforms
install_poetry_special() {
    local os="$1"
    local pkg_manager="$2"
    
    case "$os" in
        linux|macos|windows)
            # Use official installer for all platforms
            print_status "Installing Poetry using official installer..."
            curl -sSL https://install.python-poetry.org | python3 -
            return 0
            ;;
    esac
    
    # Fall back to standard package manager installation
    return 1
}

# Main installation function
main() {
    print_status "Checking Poetry installation..."
    
    if is_tool_installed "poetry"; then
        print_success "Poetry already installed: $(poetry --version)"
        return 0
    fi
    
    local os=$(detect_os)
    local pkg_manager=$(detect_package_manager "$os")
    
    print_status "Installing Poetry on $os using $pkg_manager..."
    
    # Try special installation first (official installer)
    if install_poetry_special "$os" "$pkg_manager"; then
        print_success "Poetry installed successfully"
        print_warning "You may need to add Poetry to your PATH:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        return 0
    fi
    
    # Fall back to standard installation
    case "$pkg_manager" in
        brew)
            print_status "Installing Poetry with Homebrew..."
            brew install poetry
            ;;
        apt)
            print_status "Installing Poetry with apt..."
            sudo apt-get update
            sudo apt-get install -y python3-poetry
            ;;
        yum|dnf)
            print_status "Installing Poetry with $pkg_manager..."
            sudo "$pkg_manager" install -y python3-poetry
            ;;
        pacman)
            print_status "Installing Poetry with pacman..."
            sudo pacman -S --noconfirm poetry
            ;;
        zypper)
            print_status "Installing Poetry with zypper..."
            sudo zypper install -y python3-poetry
            ;;
        winget)
            print_status "Installing Poetry with winget..."
            winget install Python.Poetry
            ;;
        choco)
            print_status "Installing Poetry with Chocolatey..."
            choco install poetry -y
            ;;
        scoop)
            print_status "Installing Poetry with Scoop..."
            scoop install poetry
            ;;
        none)
            print_error "No supported package manager found for $os"
            print_manual_install_instructions "poetry" "$os"
            return 1
            ;;
        *)
            print_error "Unknown package manager: $pkg_manager"
            return 1
            ;;
    esac
    
    print_success "Poetry installed successfully"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 