#!/bin/bash

# Docker installation script
# This script installs Docker on demand across all platforms

set -e

# Source the base installation functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/install_base.sh"

# Check if Docker is running
is_docker_running() {
    if command -v docker >/dev/null 2>&1; then
        if docker info >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Main installation function
main() {
    print_status "Checking Docker installation..."
    
    if is_docker_running; then
        print_success "Docker already installed and running: $(docker --version)"
        return 0
    fi
    
    if is_tool_installed "docker"; then
        print_warning "Docker is installed but not running. Please start Docker Desktop or Docker daemon."
        print_warning "Visit: https://docs.docker.com/get-docker/"
        return 1
    fi
    
    local os=$(detect_os)
    local pkg_manager=$(detect_package_manager "$os")
    
    print_status "Installing Docker on $os using $pkg_manager..."
    
    case "$pkg_manager" in
        brew)
            print_status "Installing Docker with Homebrew..."
            brew install --cask docker
            print_warning "Docker Desktop has been installed. Please start it manually."
            ;;
        apt)
            print_status "Installing Docker with apt..."
            sudo apt-get update
            sudo apt-get install -y ca-certificates curl gnupg lsb-release
            sudo mkdir -p /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            sudo usermod -aG docker $USER
            print_warning "Docker installed. Please log out and back in, or run: newgrp docker"
            ;;
        yum|dnf)
            print_status "Installing Docker with $pkg_manager..."
            sudo "$pkg_manager" remove docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine
            sudo "$pkg_manager" install -y dnf-utils
            sudo "$pkg_manager" config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
            sudo "$pkg_manager" install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER
            print_warning "Docker installed. Please log out and back in, or run: newgrp docker"
            ;;
        pacman)
            print_status "Installing Docker with pacman..."
            sudo pacman -S --noconfirm docker docker-compose
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER
            print_warning "Docker installed. Please log out and back in, or run: newgrp docker"
            ;;
        zypper)
            print_status "Installing Docker with zypper..."
            sudo zypper install -y docker docker-compose
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER
            print_warning "Docker installed. Please log out and back in, or run: newgrp docker"
            ;;
        winget)
            print_status "Installing Docker with winget..."
            winget install Docker.DockerDesktop
            print_warning "Docker Desktop has been installed. Please start it manually."
            ;;
        choco)
            print_status "Installing Docker with Chocolatey..."
            choco install docker-desktop -y
            print_warning "Docker Desktop has been installed. Please start it manually."
            ;;
        scoop)
            print_status "Installing Docker with Scoop..."
            scoop install docker
            print_warning "Docker has been installed. Please configure it manually."
            ;;
        none)
            print_error "No supported package manager found for $os"
            print_manual_install_instructions "docker" "$os"
            return 1
            ;;
        *)
            print_error "Unknown package manager: $pkg_manager"
            return 1
            ;;
    esac
    
    print_success "Docker installed successfully"
    print_warning "Please start Docker and ensure it's running before using Docker commands."
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 