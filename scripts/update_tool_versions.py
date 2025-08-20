#!/usr/bin/env python3
"""
Tool Version Updater
Automatically checks for latest versions of tools and updates the configuration file.
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml


class ToolVersionUpdater:
    """Updates tool versions in the configuration file."""

    def __init__(self, config_path: str | None = None):
        """Initialize the version updater.
        
        Args:
            config_path: Path to configuration file
        """
        if config_path is None:
            script_dir = Path(__file__).parent
            config_path = script_dir / "install_config.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.backup_path = self.config_path.with_suffix('.yaml.backup')

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

    def _save_config(self, config: dict[str, Any]) -> None:
        """Save configuration to YAML file."""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(f"Error: Failed to save configuration: {e}")
            sys.exit(1)

    def _create_backup(self) -> None:
        """Create a backup of the current configuration."""
        try:
            import shutil
            shutil.copy2(self.config_path, self.backup_path)
            print(f"📋 Backup created: {self.backup_path}")
        except Exception as e:
            print(f"Warning: Failed to create backup: {e}")

    def _get_github_latest_release(self, repo: str) -> str | None:
        """Get latest release version from GitHub API.
        
        Args:
            repo: Repository name (e.g., 'cli/cli' for GitHub CLI)
            
        Returns:
            Latest version string or None
        """
        try:
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            version = data.get('tag_name', '').lstrip('v')

            # Validate version format
            if re.match(r'^\d+\.\d+\.\d+', version):
                return version

        except Exception as e:
            print(f"Warning: Failed to get latest version for {repo}: {e}")

        return None

    def _get_pypi_latest_version(self, package: str) -> str | None:
        """Get latest version from PyPI.
        
        Args:
            package: Package name
            
        Returns:
            Latest version string or None
        """
        try:
            url = f"https://pypi.org/pypi/{package}/json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            version = data.get('info', {}).get('version')

            if version and re.match(r'^\d+\.\d+\.\d+', version):
                return version

        except Exception as e:
            print(f"Warning: Failed to get latest version for {package}: {e}")

        return None

    def _get_docker_latest_version(self) -> str | None:
        """Get latest Docker version (this is complex, so we'll use a simple approach).
        
        Returns:
            Latest version string or None
        """
        # Docker versions are complex and depend on the platform
        # For now, we'll return None to indicate we can't auto-update
        return None

    def _get_latest_version(self, tool_name: str) -> str | None:
        """Get latest version for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Latest version string or None
        """
        # Define version sources for each tool
        version_sources = {
            'gh': lambda: self._get_github_latest_release('cli/cli'),
            'act': lambda: self._get_github_latest_release('nektos/act'),
            'poetry': lambda: self._get_pypi_latest_version('poetry'),
            'trivy': lambda: self._get_github_latest_release('aquasecurity/trivy'),
            'docker': lambda: self._get_docker_latest_version(),
        }

        if tool_name in version_sources:
            return version_sources[tool_name]()

        return None

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

    def update_tool_version(self, tool_name: str, force: bool = False) -> bool:
        """Update version for a specific tool.
        
        Args:
            tool_name: Name of the tool
            force: Whether to force update even if current version is newer
            
        Returns:
            True if updated, False otherwise
        """
        if tool_name not in self.config.get('tools', {}):
            print(f"❌ Tool '{tool_name}' not found in configuration")
            return False

        current_version = self.config['tools'][tool_name].get('version', 'unknown')
        latest_version = self._get_latest_version(tool_name)

        if not latest_version:
            print(f"⚠️  Could not determine latest version for {tool_name}")
            return False

        if current_version == latest_version:
            print(f"✅ {tool_name}: Already at latest version ({current_version})")
            return False

        comparison = self._compare_versions(current_version, latest_version)

        if comparison > 0 and not force:
            print(f"⚠️  {tool_name}: Current version ({current_version}) is newer than latest ({latest_version})")
            print("   Use --force to update anyway")
            return False

        if comparison < 0:
            print(f"🔄 {tool_name}: Updating from {current_version} to {latest_version}")
        else:
            print(f"🔄 {tool_name}: Downgrading from {current_version} to {latest_version}")

        # Update the configuration
        self.config['tools'][tool_name]['version'] = latest_version

        return True

    def update_all_versions(self, force: bool = False) -> dict[str, bool]:
        """Update versions for all tools.
        
        Args:
            force: Whether to force update even if current version is newer
            
        Returns:
            Dictionary mapping tool names to update success status
        """
        print("🔄 Checking for tool version updates...")
        print("")

        results = {}
        tools = list(self.config.get('tools', {}).keys())

        for tool_name in tools:
            print(f"Checking {tool_name}...")
            results[tool_name] = self.update_tool_version(tool_name, force)
            print("")

        return results

    def run(self, tools: list[str] | None = None, force: bool = False) -> None:
        """Run the version updater.
        
        Args:
            tools: List of tools to update (None for all)
            force: Whether to force update even if current version is newer
        """
        print("🔧 Tool Version Updater")
        print("=" * 50)
        print(f"Configuration file: {self.config_path}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("")

        # Create backup
        self._create_backup()
        print("")

        if tools:
            # Update specific tools
            results = {}
            for tool_name in tools:
                if tool_name in self.config.get('tools', {}):
                    results[tool_name] = self.update_tool_version(tool_name, force)
                else:
                    print(f"❌ Tool '{tool_name}' not found in configuration")
                    results[tool_name] = False
        else:
            # Update all tools
            results = self.update_all_versions(force)

        # Save configuration if any updates were made
        updated_tools = [tool for tool, updated in results.items() if updated]

        if updated_tools:
            print("💾 Saving updated configuration...")
            self._save_config(self.config)
            print(f"✅ Updated {len(updated_tools)} tools: {', '.join(updated_tools)}")
        else:
            print("✅ No updates needed")

        print("")
        print("📋 Summary:")
        for tool_name, updated in results.items():
            status = "✅ Updated" if updated else "⏭️  Skipped"
            current_version = self.config['tools'][tool_name].get('version', 'unknown')
            print(f"  {tool_name}: {status} (current: {current_version})")


def main():
    """Command-line interface for the version updater."""
    import argparse

    parser = argparse.ArgumentParser(description="Update tool versions in configuration")
    parser.add_argument('tools', nargs='*', help='Specific tools to update (default: all)')
    parser.add_argument('--force', action='store_true',
                       help='Force update even if current version is newer')
    parser.add_argument('--config', help='Path to configuration file')

    args = parser.parse_args()

    updater = ToolVersionUpdater(args.config)
    updater.run(args.tools if args.tools else None, args.force)


if __name__ == "__main__":
    main()
