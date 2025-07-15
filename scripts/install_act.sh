#!/bin/bash

# Act installation script
# This script installs act (GitHub Actions local runner) on demand across all platforms

set -e

# Source the base installation functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/install_base.sh"

# Special installation for act on different platforms
install_act_special() {
    local os="$1"
    local pkg_manager="$2"
    
    case "$os" in
        linux)
            # Linux - use official install script
            print_status "Installing act using official install script..."
            curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
            return 0
            ;;
        windows)
            if [ "$pkg_manager" = "choco" ]; then
                # Windows - use Chocolatey
                print_status "Installing act with Chocolatey..."
                choco install act-cli -y
                return 0
            fi
            ;;
    esac
    
    # Fall back to standard package manager installation
    return 1
}

# Main installation function
main() {
    print_status "Checking act installation..."
    
    if is_tool_installed "act"; then
        print_success "act already installed: $(act --version)"
        return 0
    fi
    
    local os=$(detect_os)
    local pkg_manager=$(detect_package_manager "$os")
    
    print_status "Installing act on $os using $pkg_manager..."
    
    # Try special installation first
    if install_act_special "$os" "$pkg_manager"; then
        print_success "act installed successfully"
        return 0
    fi
    
    # Fall back to standard installation
    case "$pkg_manager" in
        brew)
            print_status "Installing act with Homebrew..."
            brew install act
            ;;
        apt)
            print_status "Installing act with apt..."
            # For apt, we'll use the official install script
            curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
            ;;
        yum|dnf)
            print_status "Installing act with $pkg_manager..."
            # For yum/dnf, we'll use the official install script
            curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
            ;;
        pacman)
            print_status "Installing act with pacman..."
            # For pacman, we'll use the official install script
            curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
            ;;
        zypper)
            print_status "Installing act with zypper..."
            # For zypper, we'll use the official install script
            curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
            ;;
        winget)
            print_status "Installing act with winget..."
            winget install nektos.act
            ;;
        scoop)
            print_status "Installing act with Scoop..."
            scoop install act
            ;;
        none)
            print_error "No supported package manager found for $os"
            print_manual_install_instructions "act" "$os"
            return 1
            ;;
        *)
            print_error "Unknown package manager: $pkg_manager"
            return 1
            ;;
    esac
    
    print_success "act installed successfully"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 