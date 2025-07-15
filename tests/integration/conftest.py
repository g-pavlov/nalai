#!/usr/bin/env python3
"""
Pytest configuration and common fixtures for script tests
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="function")
def temp_workspace():
    """Create a temporary workspace for testing"""
    temp_dir = tempfile.mkdtemp()
    original_cwd = os.getcwd()
    os.chdir(temp_dir)

    # Create common directory structure
    Path("packages").mkdir(exist_ok=True)
    Path("wheels").mkdir(exist_ok=True)

    yield temp_dir

    # Cleanup
    os.chdir(original_cwd)
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def mock_env_file():
    """Create a mock .env file for testing"""
    env_content = """
# Required Environment Variables
# No private registry authentication needed for tests
AUTH0_CLIENT_ID=test_auth0_client_id
AUTH0_CLIENT_SECRET=test_auth0_client_secret

# Optional Configuration
MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0
MODEL_PLATFORM=aws_bedrock
MODEL_TEMPERATURE=0
AWS_DEFAULT_REGION=us-east-1
"""
    return env_content


@pytest.fixture(scope="function")
def mock_pyproject_toml():
    """Create a mock pyproject.toml for testing"""
    pyproject_content = """
[tool.poetry]
name = "nalai"
version = "1.0.0"
description = "AI Gateway - Lean Facade for All Operations"
authors = ["Your Name <your.email@example.com>"]

[tool.poetry.dependencies]
python = "^3.8"
requests = "^2.31.0"
fastapi = "^0.104.0"
uvicorn = "^0.24.0"
local-package = {path = "packages/local-package"}

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
ruff = "^0.1.0"
black = "^23.0.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
"""
    return pyproject_content


@pytest.fixture(scope="function")
def mock_poetry_lock():
    """Create a mock poetry.lock for testing"""
    lock_content = """
[package]
[[package]]
name = "requests"
version = "2.31.0"

[[package]]
name = "fastapi"
version = "0.104.0"

[[package]]
name = "uvicorn"
version = "0.24.0"

[[package]]
name = "local-package"
version = "0.5.0"

[[package]]
name = "pytest"
version = "7.4.0"

[[package]]
name = "ruff"
version = "0.1.0"

[[package]]
name = "black"
version = "23.0.0"
"""
    return lock_content


@pytest.fixture(scope="function")
def mock_package_structure():
    """Create a mock package structure for testing"""
    packages = [
        {
            "name": "test-package-1",
            "version": "1.0.0",
            "dependencies": {"requests": "^2.31.0"},
        },
        {
            "name": "test-package-2",
            "version": "2.1.0",
            "dependencies": {"fastapi": "^0.104.0"},
        },
        {
            "name": "local-package",
            "version": "0.5.0",
            "dependencies": {"another-local": {"path": "../another-local"}},
        },
    ]
    return packages


@pytest.fixture(scope="function")
def mock_dockerfile():
    """Create a mock Dockerfile for testing"""
    dockerfile_content = """
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 nalai && \\
    chown -R nalai:nalai /app
USER nalai

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080"]
"""
    return dockerfile_content


@pytest.fixture(scope="function")
def mock_requirements_txt():
    """Create a mock requirements.txt for testing"""
    requirements_content = """
requests==2.31.0
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.5.0
python-multipart==0.0.6
"""
    return requirements_content


@pytest.fixture(scope="function")
def mock_docker_output():
    """Create mock Docker command output for testing"""
    docker_output = """
REPOSITORY          TAG                 IMAGE ID            CREATED             SIZE
nalai          analysis            abc123def456        2 minutes ago       1.2GB
nalai          prod                def456ghi789        5 minutes ago       1.1GB
nalai          dev                 ghi789jkl012        10 minutes ago       1.5GB
"""
    return docker_output


@pytest.fixture(scope="function")
def mock_docker_build_output():
    """Create mock Docker build output for testing"""
    build_output = """
#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 32B
#1 DONE 0.0s

#2 [internal] load .dockerignore
#2 transferring context: 2B
#2 DONE 0.0s

#3 [internal] load metadata for docker.io/library/python:3.12-slim
#3 DONE 0.0s

#4 [1/8] FROM docker.io/library/python:3.12-slim@sha256:abc123
#4 CACHED

#5 [internal] load build context
#5 transferring context: 2.1MB
#5 DONE 0.0s

#6 [2/8] WORKDIR /app
#6 CACHED

#7 [3/8] COPY requirements.txt .
#7 CACHED

#8 [4/8] RUN pip install --no-cache-dir -r requirements.txt
#8 CACHED

#9 [5/8] COPY . .
#9 DONE 0.0s

#10 [6/8] RUN useradd -m -u 1000 nalai
#10 DONE 0.0s

#11 [7/8] USER nalai
#11 DONE 0.0s

#12 [8/8] EXPOSE map[8080/tcp:{}]
#12 DONE 0.0s

#13 exporting to image
#13 => => exporting layers
#13 => => writing image sha256:def456
#13 => => naming to nalai:analysis

Use 'docker run' to run this container.
"""
    return build_output


@pytest.fixture(scope="function")
def mock_git_output():
    """Create mock Git command output for testing"""
    git_output = """
v2.1.0
v2.0.0
v1.5.0
v1.4.0
v1.3.0
v1.2.0
v1.1.0
v1.0.0
v0.5.0
v0.4.0
v0.3.0
v0.2.0
v0.1.0
"""
    return git_output


@pytest.fixture(scope="function")
def mock_poetry_output():
    """Create mock Poetry command output for testing"""
    poetry_output = """
requests==2.31.0
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.5.0
python-multipart==0.0.6
-e file:///app/packages/local-package
"""
    return poetry_output


@pytest.fixture(scope="function")
def mock_subprocess_success():
    """Mock successful subprocess execution"""

    class MockResult:
        def __init__(self, stdout="", stderr=""):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = stderr

    return MockResult()


@pytest.fixture(scope="function")
def mock_subprocess_failure():
    """Mock failed subprocess execution"""

    class MockResult:
        def __init__(self, stdout="", stderr="Command failed"):
            self.returncode = 1
            self.stdout = stdout
            self.stderr = stderr

    return MockResult()


@pytest.fixture(scope="function")
def mock_file_not_found():
    """Mock FileNotFoundError for testing"""
    return FileNotFoundError("No such file or directory")


@pytest.fixture(scope="function")
def mock_permission_error():
    """Mock PermissionError for testing"""
    return PermissionError("Permission denied")


@pytest.fixture(scope="function")
def mock_timeout_error():
    """Mock TimeoutError for testing"""
    return TimeoutError("Command timed out")


# Test markers for different script categories
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line("markers", "production: marks tests as production-related")
    config.addinivalue_line(
        "markers", "development: marks tests as development-related"
    )
    config.addinivalue_line("markers", "docker: marks tests as docker-related")
    config.addinivalue_line("markers", "build: marks tests as build-related")
    config.addinivalue_line("markers", "analysis: marks tests as analysis-related")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


# Common test utilities
class TestUtils:
    """Common utilities for tests"""

    @staticmethod
    def create_mock_file(path, content):
        """Create a mock file with given content"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    @staticmethod
    def create_mock_directory(path):
        """Create a mock directory"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def assert_file_exists(path):
        """Assert that a file exists"""
        assert Path(path).exists(), f"File {path} should exist"

    @staticmethod
    def assert_file_content(path, expected_content):
        """Assert that a file contains expected content"""
        actual_content = Path(path).read_text()
        assert actual_content == expected_content, f"File {path} content mismatch"

    @staticmethod
    def assert_directory_exists(path):
        """Assert that a directory exists"""
        assert Path(path).exists(), f"Directory {path} should exist"
        assert Path(path).is_dir(), f"{path} should be a directory"

    @staticmethod
    def assert_command_called_with(mock_run, expected_command):
        """Assert that a command was called with expected arguments"""
        calls = mock_run.call_args_list
        assert len(calls) > 0, "Command should have been called"

        for call in calls:
            if expected_command in str(call):
                return

        raise AssertionError(
            f"Expected command '{expected_command}' not found in calls"
        )
