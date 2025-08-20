#!/usr/bin/env python3
"""
Installation Configuration Manager
Parses and manages tool installation configuration from YAML files.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


class InstallConfig:
    """Manages tool installation configuration."""

    def __init__(self, config_path: str | None = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file. Defaults to install_config.yaml in script directory.
        """
        if config_path is None:
            script_dir = Path(__file__).parent
            config_path = script_dir / "install_config.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.os = self._detect_os()
        self.pkg_manager = self._detect_package_manager()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path) as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Error: Configuration file not found: {self.config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error: Invalid YAML in configuration file: {e}")
            sys.exit(1)

    def _detect_os(self) -> str:
        """Detect operating system."""
        import platform
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        elif system == "linux":
            return "linux"
        elif system == "windows":
            return "windows"
        else:
            return "unknown"

    def _detect_package_manager(self) -> str:
        """Detect available package manager."""
        package_managers = {
            "brew": "brew",
            "apt-get": "apt",
            "yum": "yum",
            "dnf": "dnf",
            "pacman": "pacman",
            "zypper": "zypper",
            "winget": "winget",
            "choco": "choco",
            "scoop": "scoop"
        }

        for cmd, name in package_managers.items():
            if self._command_exists(cmd):
                return name

        return "none"

    def _command_exists(self, command: str) -> bool:
        """Check if command exists in PATH."""
        try:
            subprocess.run([command, "--version"],
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_tool_config(self, tool_name: str) -> dict[str, Any] | None:
        """Get configuration for a specific tool.
        
        Args:
            tool_name: Name of the tool (gh, act, poetry, etc.)
            
        Returns:
            Tool configuration dictionary or None if not found
        """
        return self.config.get("tools", {}).get(tool_name)

    def get_package_name(self, tool_name: str, pkg_manager: str | None = None) -> str | None:
        """Get package name for a tool with the specified package manager.
        
        Args:
            tool_name: Name of the tool
            pkg_manager: Package manager name (defaults to detected one)
            
        Returns:
            Package name or None if not found
        """
        if pkg_manager is None:
            pkg_manager = self.pkg_manager

        tool_config = self.get_tool_config(tool_name)
        if not tool_config:
            return None

        return tool_config.get("package_names", {}).get(pkg_manager)

    def get_special_install_method(self, tool_name: str, os_name: str | None = None,
                                 pkg_manager: str | None = None) -> dict[str, Any] | None:
        """Get special installation method for a tool.
        
        Args:
            tool_name: Name of the tool
            os_name: Operating system (defaults to detected one)
            pkg_manager: Package manager (defaults to detected one)
            
        Returns:
            Special installation configuration or None if not found
        """
        if os_name is None:
            os_name = self.os
        if pkg_manager is None:
            pkg_manager = self.pkg_manager

        tool_config = self.get_tool_config(tool_name)
        if not tool_config:
            return None

        special_install = tool_config.get("special_install", {})

        # Check for OS-specific method
        if os_name in special_install:
            os_config = special_install[os_name]

            # Check for package manager specific method
            if pkg_manager in os_config:
                return os_config[pkg_manager]

            # Check for "all" package managers
            if "all" in os_config:
                return os_config["all"]

        # Check for "all" OS method
        if "all" in special_install:
            all_config = special_install["all"]

            # Check for package manager specific method
            if pkg_manager in all_config:
                return all_config[pkg_manager]

            # Check for "all" package managers
            if "all" in all_config:
                return all_config["all"]

        return None

    def get_required_version(self, tool_name: str) -> str | None:
        """Get required version for a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Required version string or None if not specified
        """
        tool_config = self.get_tool_config(tool_name)
        if not tool_config:
            return None

        return tool_config.get("version")

    def get_min_version(self, tool_name: str) -> str | None:
        """Get minimum required version for a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Minimum version string or None if not specified
        """
        tool_config = self.get_tool_config(tool_name)
        if not tool_config:
            return None

        return tool_config.get("min_version")

    def get_version_check_command(self, tool_name: str) -> str | None:
        """Get command to check tool version.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Version check command or None if not specified
        """
        tool_config = self.get_tool_config(tool_name)
        if not tool_config:
            return None

        return tool_config.get("version_check")

    def get_current_version(self, tool_name: str) -> str | None:
        """Get current installed version of a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Current version string or None if not installed
        """
        version_check = self.get_version_check_command(tool_name)
        if not version_check:
            return None

        try:
            result = subprocess.run(version_check, shell=True,
                                  capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def is_version_compatible(self, tool_name: str, current_version: str | None = None) -> bool:
        """Check if current version is compatible with required version.
        
        Args:
            tool_name: Name of the tool
            current_version: Current version (defaults to detected version)
            
        Returns:
            True if version is compatible, False otherwise
        """
        if current_version is None:
            current_version = self.get_current_version(tool_name)

        if not current_version:
            return False

        min_version = self.get_min_version(tool_name)
        if not min_version:
            return True  # No minimum version specified, assume compatible

        return self._compare_versions(current_version, min_version) >= 0

    def _compare_versions(self, version1: str, version2: str) -> int:
        """Compare two version strings.
        
        Args:
            version1: First version string
            version2: Second version string
            
        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        def normalize_version(v):
            return [int(x) for x in re.sub(r'[^\d.]', '', v).split('.')]

        v1_parts = normalize_version(version1)
        v2_parts = normalize_version(version2)

        # Pad with zeros to make lengths equal
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        for i in range(max_len):
            if v1_parts[i] < v2_parts[i]:
                return -1
            elif v1_parts[i] > v2_parts[i]:
                return 1

        return 0

    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """Get global configuration setting.
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        return self.config.get("global", {}).get(key, default)

    def get_platform_setting(self, key: str, default: Any = None) -> Any:
        """Get platform-specific configuration setting.
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        platform_config = self.config.get("platform_overrides", {}).get(self.os, {})
        return platform_config.get(key, default)

    def get_environment_setting(self, environment: str, key: str, default: Any = None) -> Any:
        """Get environment-specific configuration setting.
        
        Args:
            environment: Environment name (development, ci, production)
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        env_config = self.config.get("environments", {}).get(environment, {})
        return env_config.get(key, default)

    def list_available_tools(self) -> list[str]:
        """Get list of all available tools in configuration.
        
        Returns:
            List of tool names
        """
        return list(self.config.get("tools", {}).keys())

    def get_tool_info(self, tool_name: str) -> dict[str, Any]:
        """Get comprehensive information about a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Dictionary with tool information
        """
        tool_config = self.get_tool_config(tool_name)
        if not tool_config:
            return {}

        current_version = self.get_current_version(tool_name)
        is_compatible = self.is_version_compatible(tool_name, current_version)

        return {
            "name": tool_config.get("name", tool_name),
            "required_version": self.get_required_version(tool_name),
            "min_version": self.get_min_version(tool_name),
            "current_version": current_version,
            "is_installed": current_version is not None,
            "is_compatible": is_compatible,
            "package_name": self.get_package_name(tool_name),
            "special_install": self.get_special_install_method(tool_name)
        }


def main():
    """Command-line interface for configuration management."""
    if len(sys.argv) < 2:
        print("Usage: python install_config.py <command> [args...]")
        print("Commands:")
        print("  list-tools                    - List all available tools")
        print("  tool-info <tool>              - Show detailed tool information")
        print("  get-package-name <tool>       - Get package name for current platform")
        print("  get-version <tool>            - Get current installed version")
        print("  check-compatibility <tool>    - Check if current version is compatible")
        print("  get-install-method <tool>     - Get installation method for current platform")
        return

    config = InstallConfig()
    command = sys.argv[1]

    if command == "list-tools":
        tools = config.list_available_tools()
        for tool in tools:
            print(tool)

    elif command == "tool-info" and len(sys.argv) > 2:
        tool_name = sys.argv[2]
        info = config.get_tool_info(tool_name)
        if info:
            print(f"Tool: {info['name']}")
            print(f"Required version: {info['required_version']}")
            print(f"Minimum version: {info['min_version']}")
            print(f"Current version: {info['current_version']}")
            print(f"Installed: {info['is_installed']}")
            print(f"Compatible: {info['is_compatible']}")
            print(f"Package name: {info['package_name']}")
            if info['special_install']:
                print(f"Special install method: {info['special_install']['method']}")
        else:
            print(f"Tool '{tool_name}' not found in configuration")

    elif command == "get-package-name" and len(sys.argv) > 2:
        tool_name = sys.argv[2]
        package_name = config.get_package_name(tool_name)
        print(package_name or "Not found")

    elif command == "get-version" and len(sys.argv) > 2:
        tool_name = sys.argv[2]
        version = config.get_current_version(tool_name)
        print(version or "Not installed")

    elif command == "check-compatibility" and len(sys.argv) > 2:
        tool_name = sys.argv[2]
        compatible = config.is_version_compatible(tool_name)
        print("Compatible" if compatible else "Incompatible")

    elif command == "get-install-method" and len(sys.argv) > 2:
        tool_name = sys.argv[2]
        method = config.get_special_install_method(tool_name)
        if method:
            print(f"Method: {method['method']}")
            for key, value in method.items():
                if key != "method":
                    print(f"  {key}: {value}")
        else:
            print("No special install method configured")

    else:
        print("Invalid command or missing arguments")
        print("Run without arguments to see usage")


if __name__ == "__main__":
    main()
