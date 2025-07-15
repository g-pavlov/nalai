#!/bin/bash

# Trivy installation script
# This script installs Trivy (security scanner) on demand across all platforms

set -e

# Source the base installation functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/install_base.sh"

# Special installation for Trivy on different platforms
install_trivy_special() {
    local os="$1"
    local pkg_manager="$2"
    
    case "$os" in
        linux|macos|windows)
            # Use official installer for all platforms
            print_status "Installing Trivy using official installer..."
            curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
            return 0
            ;;
    esac
    
    # Fall back to standard package manager installation
    return 1
}

# Main installation function
main() {
    print_status "Checking Trivy installation..."
    
    if is_tool_installed "trivy"; then
        print_success "Trivy already installed: $(trivy --version | head -1)"
        return 0
    fi
    
    local os=$(detect_os)
    local pkg_manager=$(detect_package_manager "$os")
    
    print_status "Installing Trivy on $os using $pkg_manager..."
    
    # Try special installation first (official installer)
    if install_trivy_special "$os" "$pkg_manager"; then
        print_success "Trivy installed successfully"
        return 0
    fi
    
    # Fall back to standard installation
    case "$pkg_manager" in
        brew)
            print_status "Installing Trivy with Homebrew..."
            brew install trivy
            ;;
        apt)
            print_status "Installing Trivy with apt..."
            sudo apt-get update
            sudo apt-get install -y wget apt-transport-https gnupg lsb-release
            wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
            echo deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main | sudo tee -a /etc/apt/sources.list.d/trivy.list
            sudo apt-get update
            sudo apt-get install -y trivy
            ;;
        yum|dnf)
            print_status "Installing Trivy with $pkg_manager..."
            sudo "$pkg_manager" install -y wget
            wget -qO - https://aquasecurity.github.io/trivy-repo/rpm/public.key | sudo rpm --import -
            echo -e "[trivy]\nname=Trivy repository\nbaseurl=https://aquasecurity.github.io/trivy-repo/rpm/release/\$releasever/\$basearch/\ngpgcheck=1\nenabled=1" | sudo tee /etc/yum.repos.d/trivy.repo
            sudo "$pkg_manager" install -y trivy
            ;;
        pacman)
            print_status "Installing Trivy with pacman..."
            sudo pacman -S --noconfirm trivy
            ;;
        zypper)
            print_status "Installing Trivy with zypper..."
            sudo zypper install -y trivy
            ;;
        winget)
            print_status "Installing Trivy with winget..."
            winget install AquaSecurity.Trivy
            ;;
        choco)
            print_status "Installing Trivy with Chocolatey..."
            choco install trivy -y
            ;;
        scoop)
            print_status "Installing Trivy with Scoop..."
            scoop install trivy
            ;;
        none)
            print_error "No supported package manager found for $os"
            print_manual_install_instructions "trivy" "$os"
            return 1
            ;;
        *)
            print_error "Unknown package manager: $pkg_manager"
            return 1
            ;;
    esac
    
    print_success "Trivy installed successfully"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 