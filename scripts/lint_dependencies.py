#!/usr/bin/env python3
"""
Dependency Linting Script
Checks for dev dependencies in wrong places using heuristics and known patterns
"""

import glob
import re
import sys
import tomllib

# Known dev-only packages (common ones)
DEV_ONLY_PACKAGES = {
    'pytest', 'pytest-cov', 'pytest-mock', 'pytest-asyncio', 'pytest-xdist',
    'coverage', 'deepeval', 'testcontainers', 'ruff', 'black', 'flake8', 'mypy',
    'ipython', 'jupyter', 'notebook', 'ipdb', 'pdbpp', 'sphinx', 'mkdocs',
    'setuptools', 'wheel', 'build', 'twine', 'tox', 'nox', 'pre-commit',
}

# Heuristic patterns for dev dependencies
DEV_PATTERNS = [
    r'test', r'mock', r'fake', r'debug', r'dev', r'debugger',
    r'coverage', r'cov', r'assert', r'validate',
    r'format', r'lint', r'style', r'type', r'types-',
    r'doc', r'docs', r'sphinx', r'mkdocs', r'pdoc',
    r'build', r'wheel', r'setuptools', r'twine',
    r'pre-commit', r'tox', r'nox', r'pytest',
]

def get_all_dev_dependencies():
    """Extract all dev dependencies from all pyproject.toml files"""
    all_dev_deps = set()

    # Check main pyproject.toml
    main_data = load_pyproject_toml('pyproject.toml')
    if main_data and 'tool' in main_data and 'poetry' in main_data['tool']:
        poetry = main_data['tool']['poetry']
        if 'group' in poetry and 'dev' in poetry['group']:
            dev_group = poetry['group']['dev']
            if 'dependencies' in dev_group:
                all_dev_deps.update(dev_group['dependencies'].keys())

    # Check package pyproject.toml files (if any exist in the future)
    for pkg_file in glob.glob('packages/*/pyproject.toml'):
        pkg_data = load_pyproject_toml(pkg_file)
        if pkg_data and 'tool' in pkg_data and 'poetry' in pkg_data['tool']:
            poetry = pkg_data['tool']['poetry']
            if 'group' in poetry and 'dev' in poetry['group']:
                dev_group = poetry['group']['dev']
                if 'dependencies' in dev_group:
                    all_dev_deps.update(dev_group['dependencies'].keys())

    return all_dev_deps

def is_likely_dev_dependency(package_name, project_dev_deps):
    """Use heuristics and project classification to determine if a package is likely a dev dependency"""

    # Check if already classified as dev in this project
    if package_name in project_dev_deps:
        return True, "already classified as dev in project"

    # Check known dev packages
    if package_name in DEV_ONLY_PACKAGES:
        return True, "known dev package"

    # Check patterns
    for pattern in DEV_PATTERNS:
        if re.search(pattern, package_name.lower()):
            return True, f"matches pattern '{pattern}'"

    # Check for type stubs (types-* packages)
    if package_name.startswith('types-'):
        return True, "type stub package"

    # Check for testing frameworks
    if any(test_framework in package_name.lower() for test_framework in ['test', 'spec', 'assert']):
        return True, "testing-related"

    return False, None

def check_dependencies(data, file_path, project_dev_deps):
    """Check for dev dependencies in wrong places"""
    errors = []
    warnings = []

    if 'tool' not in data or 'poetry' not in data['tool']:
        return errors, warnings

    poetry = data['tool']['poetry']

    # Check main dependencies for likely dev packages
    if 'dependencies' in poetry:
        main_deps = poetry['dependencies']
        for dep in main_deps:
            is_dev, reason = is_likely_dev_dependency(dep, project_dev_deps)
            if is_dev:
                errors.append(f"❌ {dep} looks like a dev dependency ({reason})")

    # Check if dev group exists
    if 'group' in poetry and 'dev' in poetry['group']:
        dev_group = poetry['group']['dev']
        if 'dependencies' not in dev_group:
            warnings.append("⚠️  Dev group exists but has no dependencies")
    else:
        warnings.append("⚠️  No dev group found - consider adding one")

    return errors, warnings

def main():
    """Main linting function"""
    print("🔍 Linting dependencies using heuristics and project classification...")

    # Get all dev dependencies from the project
    project_dev_deps = get_all_dev_dependencies()
    print(f"📋 Found {len(project_dev_deps)} dev dependencies across project: {', '.join(sorted(project_dev_deps))}")

    all_errors = []
    all_warnings = []

    # Check main pyproject.toml
    main_data = load_pyproject_toml('pyproject.toml')
    if main_data:
        errors, warnings = check_dependencies(main_data, 'pyproject.toml', project_dev_deps)
        if errors or warnings:
            print("\n📦 Main pyproject.toml:")
            for error in errors:
                print(f"  {error}")
            for warning in warnings:
                print(f"  {warning}")
            all_errors.extend(errors)
            all_warnings.extend(warnings)

    # Check package pyproject.toml files (if any exist in the future)
    for pkg_file in glob.glob('packages/*/pyproject.toml'):
        pkg_data = load_pyproject_toml(pkg_file)
        if pkg_data:
            errors, warnings = check_dependencies(pkg_data, pkg_file, project_dev_deps)
            if errors or warnings:
                print(f"\n📦 {pkg_file}:")
                for error in errors:
                    print(f"  {error}")
                for warning in warnings:
                    print(f"  {warning}")
                all_errors.extend(errors)
                all_warnings.extend(warnings)

    if all_errors:
        print(f"\n❌ Found {len(all_errors)} dependency errors")
        print("\n💡 Recommendations:")
        print("  - Review flagged packages - are they really needed in production?")
        print("  - Move dev packages to [tool.poetry.group.dev.dependencies]")
        print("  - Run 'poetry lock --no-update' to regenerate lockfile")
        sys.exit(1)
    elif all_warnings:
        print(f"\n⚠️  Found {len(all_warnings)} warnings (non-blocking)")
        print("💡 Consider adding dev groups to packages for better organization")
    else:
        print("✅ All dependency checks passed!")

def load_pyproject_toml(file_path):
    """Load and parse a pyproject.toml file"""
    try:
        with open(file_path, 'rb') as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return None

if __name__ == "__main__":
    main()
