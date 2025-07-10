#!/usr/bin/env python3
"""
Generate a clean requirements.txt file from poetry.lock without local packages.
This script reads the poetry.lock file and extracts only external dependencies.
"""

import re
import sys
from pathlib import Path


def extract_external_dependencies():
    """Extract external dependencies from poetry.lock file."""
    lock_file = Path("poetry.lock")

    if not lock_file.exists():
        print("❌ poetry.lock file not found!")
        sys.exit(1)

    print("📋 Reading poetry.lock file...")

    with open(lock_file) as f:
        content = f.read()

    # Find all package sections
    package_sections = re.findall(r'\[\[package\]\]\n(.*?)(?=\n\[\[package\]\]|\n\[|$)', content, re.DOTALL)

    external_deps = []

    for section in package_sections:
        # Extract package name and version
        name_match = re.search(r'name = "([^"]+)"', section)
        version_match = re.search(r'version = "([^"]+)"', section)

        if name_match and version_match:
            name = name_match.group(1)
            version = version_match.group(1)

            # Skip local packages (those with file:// paths)
            if 'source = {file = "' in section:
                print(f"🔄 Skipping local package: {name}")
                continue

            # Skip packages from private sources (if any)
            if 'source = ' in section and 'private' in section.lower():
                print(f"🔄 Skipping private package: {name}")
                continue

            external_deps.append(f"{name}=={version}")

    return sorted(external_deps)


def write_requirements_file(dependencies, output_file="requirements.txt"):
    """Write dependencies to requirements.txt file."""
    print(f"📝 Writing {len(dependencies)} external dependencies to {output_file}...")

    with open(output_file, "w") as f:
        for dep in dependencies:
            f.write(f"{dep}\n")

    print(f"✅ Generated {output_file} with {len(dependencies)} external dependencies")


def main():
    """Main function."""
    print("🚀 Generating clean requirements.txt from poetry.lock...")

    # Extract external dependencies
    dependencies = extract_external_dependencies()

    if not dependencies:
        print("❌ No external dependencies found!")
        sys.exit(1)

    # Write to requirements.txt
    write_requirements_file(dependencies)

    print("\n📋 Summary:")
    print(f"   - Total external dependencies: {len(dependencies)}")
    print("   - Output file: requirements.txt")
    print("\n💡 Note: Local packages and private packages were excluded.")
    print("   Use 'poetry install' to install local packages.")


if __name__ == "__main__":
    main()
