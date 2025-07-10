#!/usr/bin/env python3
"""
Generate production requirements.txt with non-editable local packages.
This script exports dependencies from poetry and converts local packages to non-editable format.
"""

import re
import subprocess
import sys


def run_command(cmd, check=True):
    """Run a command and return the result."""
    print(f"🔧 Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result


def generate_prod_requirements():
    """Generate production requirements.txt with non-editable local packages."""
    print("🚀 Generating production requirements.txt...")

    # Step 1: Export dependencies from poetry
    print("📋 Exporting dependencies from poetry...")
    run_command("poetry export --without-hashes --without-urls --without=dev -o requirements.txt")

    # Step 2: Convert editable installs to non-editable
    print("🔄 Converting local packages to non-editable format...")

    with open("requirements.txt") as f:
        content = f.read()

    # Replace editable installs with non-editable and Docker path
    # From: -e file:///Users/gpavlov/dev/ai-gateway/packages/package-name
    # To:   file:///app/packages/package-name
    def replace_local(match):
        original = match.group(0)
        pkg = match.group(1)
        print(f"🔄 Replacing local package: {original} -> file:///app/packages/{pkg}")
        return f"file:///app/packages/{pkg}"

    # Match any -e file://.../packages/package-name (with optional extras/markers)
    modified_content = re.sub(
        r"^-e file://.*?/packages/([^/\s;]+)(.*)$",
        lambda m: replace_local(m) + m.group(2),
        content,
        flags=re.MULTILINE
    )

    # Write the modified requirements.txt
    with open("requirements.txt", "w") as f:
        f.write(modified_content)

    print("✅ Production requirements.txt generated successfully!")
    print("📦 Local packages will be installed as non-editable packages")
    print("🔧 Use this file in your Docker build with:")
    print("   COPY packages/ /app/packages/")
    print("   COPY requirements.txt .")
    print("   RUN pip install -r requirements.txt")


def main():
    """Main function."""
    try:
        generate_prod_requirements()
    except Exception as e:
        print(f"❌ Error generating production requirements: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
