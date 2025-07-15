#!/bin/bash

# GitHub CLI installation script
# This script installs GitHub CLI (gh) on demand across all platforms

set -e

# Source the base installation functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/install_base.sh"

# Special installation for GitHub CLI on different platforms
install_gh_special() {
    local os="$1"
    local pkg_manager="$2"
    
    case "$os" in
        linux)
            if [ "$pkg_manager" = "apt" ]; then
                # Ubuntu/Debian - use official repository
                print_status "Installing GitHub CLI from official repository..."
                curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
                echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
                sudo apt-get update
                sudo apt-get install gh -y
                return 0
            fi
            ;;
        windows)
            if [ "$pkg_manager" = "winget" ]; then
                # Windows - use winget with correct package name
                print_status "Installing GitHub CLI with winget..."
                winget install GitHub.cli
                return 0
            fi
            ;;
    esac
    
    # Fall back to standard package manager installation
    return 1
}

# Main installation function
main() {
    print_status "Checking GitHub CLI installation..."
    
    # Get configuration using Python script
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local config_script="$script_dir/install_config.py"
    
    if [ -f "$config_script" ] && command -v python3 >/dev/null 2>&1; then
        # Use configuration-based installation
        local package_name=$(python3 "$config_script" get-package-name "gh")
        local special_method=$(python3 "$config_script" get-install-method "gh")
        
        if [ -n "$package_name" ]; then
            print_status "Using configuration-based installation for GitHub CLI"
            
            # Check if already installed and compatible
            if is_tool_installed "gh"; then
                local is_compatible=$(python3 "$config_script" check-compatibility "gh")
                if [ "$is_compatible" = "Compatible" ]; then
                    local current_version=$(gh --version | head -1)
                    print_success "GitHub CLI already installed and compatible: $current_version"
                    return 0
                fi
            fi
            
            # Try special installation method first
            if [ -n "$special_method" ]; then
                print_status "Using special installation method: $special_method"
                if install_gh_special "$(detect_os)" "$(detect_package_manager "$(detect_os)")"; then
                    print_success "GitHub CLI installed successfully"
                    return 0
                fi
            fi
            
            # Fall back to package manager installation
            install_tool "gh" "$package_name"
            return $?
        fi
    fi
    
    # Fallback to original logic if configuration not available
    if is_tool_installed "gh"; then
        print_success "GitHub CLI already installed: $(gh --version | head -1)"
        return 0
    fi
    
    local os=$(detect_os)
    local pkg_manager=$(detect_package_manager "$os")
    
    print_status "Installing GitHub CLI on $os using $pkg_manager..."
    
    # Try special installation first
    if install_gh_special "$os" "$pkg_manager"; then
        print_success "GitHub CLI installed successfully"
        return 0
    fi
    
    # Fall back to standard installation
    case "$pkg_manager" in
        brew)
            print_status "Installing GitHub CLI with Homebrew..."
            brew install gh
            ;;
        yum|dnf)
            print_status "Installing GitHub CLI with $pkg_manager..."
            sudo "$pkg_manager" install -y gh
            ;;
        pacman)
            print_status "Installing GitHub CLI with pacman..."
            sudo pacman -S --noconfirm github-cli
            ;;
        zypper)
            print_status "Installing GitHub CLI with zypper..."
            sudo zypper install -y gh
            ;;
        choco)
            print_status "Installing GitHub CLI with Chocolatey..."
            choco install gh -y
            ;;
        scoop)
            print_status "Installing GitHub CLI with Scoop..."
            scoop install gh
            ;;
        none)
            print_error "No supported package manager found for $os"
            print_manual_install_instructions "gh" "$os"
            return 1
            ;;
        *)
            print_error "Unknown package manager: $pkg_manager"
            return 1
            ;;
    esac
    
    print_success "GitHub CLI installed successfully"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 