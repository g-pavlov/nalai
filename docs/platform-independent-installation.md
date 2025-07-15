# Platform-Independent Installation System

This project includes a comprehensive, platform-independent installation system that automatically installs required tools across all major operating systems.

## Overview

The installation system provides:
- **Transparent installation** - Tools are installed automatically when needed
- **Platform support** - Works on macOS, Linux, and Windows
- **Package manager detection** - Automatically detects and uses the best package manager
- **Fallback mechanisms** - Uses official installers when package managers aren't available
- **Clear error messages** - Provides helpful instructions for manual installation when needed

## Supported Platforms

### macOS
- **Package Manager**: Homebrew (`brew`)
- **Fallback**: Official installers via curl

### Linux
- **Package Managers**: 
  - `apt` (Ubuntu, Debian)
  - `yum` (RHEL, CentOS)
  - `dnf` (Fedora)
  - `pacman` (Arch Linux)
  - `zypper` (openSUSE)
- **Fallback**: Official installers via curl

### Windows
- **Package Managers**:
  - `winget` (Windows Package Manager)
  - `choco` (Chocolatey)
  - `scoop` (Scoop)
- **Fallback**: Official installers

## Available Tools

### On-Demand Tools (Installed When Needed)

| Tool | Purpose | Installation Trigger |
|------|---------|-------------------|
| `gh` | GitHub CLI | `make test-gh-actions` |
| `act` | GitHub Actions local runner | `make test-gh-actions` |

### Hard Dependencies (Installed During Setup)

| Tool | Purpose | Installation Trigger |
|------|---------|-------------------|
| `poetry` | Python package manager | `make setup-dev` |
| `trivy` | Security scanner | `make setup-dev` |

### Optional Tools (Recommended)

| Tool | Purpose | Installation Trigger |
|------|---------|-------------------|
| `docker` | Containerization | Manual: `./scripts/install_docker.sh` |

## Installation Scripts

### Base Installation Script
- **File**: `scripts/install_base.sh`
- **Purpose**: Common functions for platform detection and package management
- **Functions**:
  - `detect_os()` - Detects operating system
  - `detect_package_manager()` - Finds available package manager
  - `install_package()` - Installs packages using detected manager
  - `print_manual_install_instructions()` - Shows manual installation steps

### Tool-Specific Scripts

#### `scripts/install_gh.sh`
- Installs GitHub CLI
- Uses official repository for Ubuntu/Debian
- Falls back to package manager installation

#### `scripts/install_act.sh`
- Installs act (GitHub Actions local runner)
- Uses official install script for Linux
- Falls back to package manager installation

#### `scripts/install_poetry.sh`
- Installs Poetry (Python package manager)
- Uses official installer for all platforms
- Falls back to package manager installation

#### `scripts/install_trivy.sh`
- Installs Trivy (security scanner)
- Uses official installer for all platforms
- Falls back to package manager installation

#### `scripts/install_docker.sh`
- Installs Docker
- Platform-specific installation methods
- Handles Docker Desktop vs Docker Engine

## Usage

### For Developers

**Automatic Installation (Recommended):**
```bash
# Setup development environment (installs hard dependencies)
make setup-dev

# Test GitHub Actions (installs on-demand tools)
make test-gh-actions
```

**Manual Installation (if needed):**
```bash
# Install specific tools manually
./scripts/install_gh.sh
./scripts/install_act.sh
./scripts/install_poetry.sh
./scripts/install_trivy.sh
./scripts/install_docker.sh
```

### For CI/CD

The installation scripts are designed to be idempotent and safe to run multiple times:
```bash
# Safe to run in CI environments
./scripts/install_gh.sh
./scripts/install_act.sh
```

## Installation Logic

### 1. Tool Detection
Each script first checks if the tool is already installed:
```bash
if is_tool_installed "gh"; then
    print_success "GitHub CLI already installed: $(gh --version | head -1)"
    return 0
fi
```

### 2. Platform Detection
Detects the operating system and available package manager:
```bash
local os=$(detect_os)
local pkg_manager=$(detect_package_manager "$os")
```

### 3. Installation Strategy
1. **Try special installation** (official installers, repositories)
2. **Fall back to package manager** (brew, apt, yum, etc.)
3. **Provide manual instructions** if no method is available

### 4. Error Handling
- Clear error messages for unsupported platforms
- Links to official installation instructions
- Graceful fallbacks when package managers fail

## Package Manager Support

### macOS
```bash
# Homebrew
brew install <package>
```

### Linux
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y <package>

# RHEL/CentOS
sudo yum install -y <package>

# Fedora
sudo dnf install -y <package>

# Arch Linux
sudo pacman -S --noconfirm <package>

# openSUSE
sudo zypper install -y <package>
```

### Windows
```bash
# Windows Package Manager
winget install <package>

# Chocolatey
choco install <package> -y

# Scoop
scoop install <package>
```

## Error Handling

### Unsupported Platform
```bash
print_error "No supported package manager found for $os"
print_manual_install_instructions "gh" "$os"
```

### Package Manager Not Found
```bash
print_warning "Homebrew not found. Please install Homebrew first:"
echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
```

### Installation Failure
```bash
print_error "Failed to install $tool"
return 1
```

## Best Practices

### For Tool Installation
1. **Always check if tool exists** before attempting installation
2. **Use official installers** when available
3. **Provide clear fallback instructions**
4. **Handle platform-specific requirements**

### For Script Development
1. **Source the base script** for common functions
2. **Use consistent error handling**
3. **Provide helpful error messages**
4. **Test on multiple platforms**

### For Users
1. **Use automatic installation** when possible
2. **Follow manual instructions** if automatic fails
3. **Report issues** with specific platform details

## Troubleshooting

### Common Issues

**Tool not found after installation:**
```bash
# Check if tool is in PATH
which <tool>

# Add to PATH if needed
export PATH="$HOME/.local/bin:$PATH"
```

**Permission denied:**
```bash
# Make script executable
chmod +x scripts/install_*.sh

# Run with sudo if needed
sudo ./scripts/install_<tool>.sh
```

**Package manager not detected:**
```bash
# Check available package managers
command -v brew
command -v apt-get
command -v yum
```

### Platform-Specific Issues

**macOS:**
- Ensure Homebrew is installed
- Check Xcode Command Line Tools

**Linux:**
- Update package manager: `sudo apt-get update`
- Install build tools if needed

**Windows:**
- Run as Administrator for some installations
- Ensure WSL2 is configured for Docker

## Contributing

### Adding New Tools

1. **Create installation script** in `scripts/install_<tool>.sh`
2. **Source the base script** for common functions
3. **Implement platform-specific logic**
4. **Add to documentation**
5. **Test on multiple platforms**

### Example Template
```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/install_base.sh"

main() {
    print_status "Checking <tool> installation..."
    
    if is_tool_installed "<tool>"; then
        print_success "<tool> already installed: $($tool --version)"
        return 0
    fi
    
    local os=$(detect_os)
    local pkg_manager=$(detect_package_manager "$os")
    
    # Platform-specific installation logic here
    
    print_success "<tool> installed successfully"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

## Summary

The platform-independent installation system provides:
- **Seamless developer experience** across all platforms
- **Automatic tool management** with transparent installation
- **Robust error handling** with clear fallback instructions
- **Extensible architecture** for adding new tools
- **CI/CD friendly** with idempotent installation scripts

This system ensures that developers can focus on their work rather than tool installation, while providing clear guidance when manual intervention is needed. 