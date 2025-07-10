#!/usr/bin/env python3
"""
Optimized wheel building script that combines the best features of both versions.
This script builds wheels for all packages and exports requirements in a single pass,
with support for export-only mode and private package detection.
"""

import shutil
import subprocess
from pathlib import Path

import tomlkit

PACKAGES_DIR = Path("packages")
WHEELS_DIR = Path("wheels")
REQUIREMENTS_FILE = Path("requirements.txt")


def run_command(cmd, cwd=None):
    """Run a shell command and return the result."""
    print(f"🔧 Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        print(f"Error: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def get_package_versions():
    """Extract package versions from all package pyproject.toml files."""
    package_versions = {}

    for package_dir in PACKAGES_DIR.iterdir():
        if package_dir.is_dir():
            pyproject_path = package_dir / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path) as f:
                    data = tomlkit.load(f)

                package_name = data["tool"]["poetry"]["name"]
                version = data["tool"]["poetry"]["version"]
                package_versions[package_name] = version
                print(f"📦 Found package: {package_name} v{version}")

    return package_versions


def build_package_wheel(package_dir):
    """Build a wheel for a single package using production config."""
    package_name = package_dir.name
    pyproject_path = package_dir / "pyproject.toml"
    prod_pyproject_path = package_dir / "pyproject_prod.toml"

    print(f"\n🔄 Building wheel for {package_name}...")

    # Use production config if available, otherwise use regular config
    config_to_use = prod_pyproject_path if prod_pyproject_path.exists() else pyproject_path

    # Create a temporary backup and replace the pyproject.toml
    backup_path = package_dir / "pyproject.toml.backup"
    if pyproject_path.exists():
        shutil.copy2(pyproject_path, backup_path)

    try:
        # Replace with production config
        if config_to_use != pyproject_path:
            shutil.copy2(config_to_use, pyproject_path)

        # Build the wheel
        run_command("poetry build", cwd=package_dir)

        # Move wheel to central location
        dist_dir = package_dir / "dist"
        if dist_dir.exists():
            for wheel_file in dist_dir.glob("*.whl"):
                target_path = WHEELS_DIR / wheel_file.name
                shutil.move(str(wheel_file), str(target_path))
                print(f"✅ Wheel built: {wheel_file.name}")

            # Clean up dist directory
            shutil.rmtree(dist_dir)

    finally:
        # Restore original pyproject.toml
        if backup_path.exists():
            shutil.move(backup_path, pyproject_path)


def export_requirements():
    """Export external dependencies to requirements.txt for Docker builds"""
    print("📋 Generating requirements.txt (external dependencies only)...")

    # Use poetry export without hashes for Docker builds
    cmd = ["poetry", "export", "-f", "requirements.txt", "--without-hashes", "--without-urls"]

    print(f"🔧 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Error exporting requirements: {result.stderr}")
        return False

    # Filter out local packages and invalid lines
    lines = result.stdout.split('\n')
    filtered_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip local package references
        if line.startswith('-e file://'):
            package_name = line.split('/')[-1].split(';')[0]
            print(f"🔄 Skipping local package: {line}")
            continue

        # Skip invalid lines
        if line.startswith('--extra-index-url'):
            print(f"⚠️  Skipping invalid/local package line: {line}")
            continue

        filtered_lines.append(line)

    # Write filtered requirements
    with open('requirements.txt', 'w') as f:
        f.write('\n'.join(filtered_lines))

    print("✅ External dependencies exported to requirements.txt")
    print("📦 Local packages will be installed from wheels/")
    return True


def check_private_packages():
    """Check and handle private packages."""
    print("🔍 Checking for private packages...")

    # Read the main pyproject.toml to find private packages
    with open("pyproject.toml") as f:
        data = tomlkit.load(f)

    dependencies = data["tool"]["poetry"].get("dependencies", {})
    private_packages = []

    for package, config in dependencies.items():
        if isinstance(config, dict) and "source" in config:
            source = config["source"]
            version = config.get("version", "latest")
            private_packages.append((package, source, version))
            print(f"📦 Found private package: {package} v{version} from {source}")

    return private_packages


def main():
    """Main function to build all wheels and export requirements."""
    import sys

    export_only = "--export-only" in sys.argv

    if export_only:
        print("📋 Exporting requirements.txt only (wheels already built)...")
    else:
        print("🏗️  Starting optimized wheel building process...")
        # Create wheels directory
        WHEELS_DIR.mkdir(exist_ok=True)

        # Get package versions first
        package_versions = get_package_versions()

        # Check for private packages
        private_packages = check_private_packages()

        if private_packages:
            print("⚠️  Private packages detected. These will be handled by the build system.")
            print("   Make sure private registry authentication is properly configured.")

        # Build wheels for each package
        for package_dir in PACKAGES_DIR.iterdir():
            if package_dir.is_dir() and (package_dir / "pyproject.toml").exists():
                try:
                    build_package_wheel(package_dir)
                except Exception as e:
                    print(f"❌ Failed to build wheel for {package_dir.name}: {e}")
                    continue

    # Export requirements.txt
    export_requirements()

    if export_only:
        print("✅ Requirements export completed!")
    else:
        print("\n🎉 Optimized wheel building process completed!")
        print(f"📦 Wheels available in: {WHEELS_DIR}")
        print(f"📋 Requirements file: {REQUIREMENTS_FILE}")

        # Check for private packages again for final message
        if not export_only:
            private_packages = check_private_packages()
            if private_packages:
                print("\n⚠️  Note: Private packages will be installed during Docker build")
                print("   using the configured private registry authentication.")


if __name__ == "__main__":
    main()
