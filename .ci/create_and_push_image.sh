#!/bin/bash

# Docker Build and Push Script for GitLab CI
# ==========================================
# This script handles Docker image building and registry pushing

set -e

echo "Building and pushing container image to registry"

# Check if INCREMENTED_VERSION is set, if not try to read from build.env
if [ -z "$INCREMENTED_VERSION" ]; then
    if [ -f "build.env" ]; then
        echo "INCREMENTED_VERSION not set, reading from build.env file..."
        source build.env
        echo "Loaded INCREMENTED_VERSION from build.env: $INCREMENTED_VERSION"
    else
        echo "Error: INCREMENTED_VERSION not set and build.env file not found"
        exit 1
    fi
fi

# Validate required environment variables
if [ -z "$INCREMENTED_VERSION" ] || [ -z "$CI_REGISTRY_IMAGE" ]; then
    echo "Error: Required environment variables are missing"
    echo "INCREMENTED_VERSION: $INCREMENTED_VERSION"
    echo "CI_REGISTRY_IMAGE: $CI_REGISTRY_IMAGE"
    exit 1
fi

# CI_COMMIT_SHA might not be available in all contexts, use git as fallback
if [ -z "$CI_COMMIT_SHA" ]; then
    echo "Warning: CI_COMMIT_SHA not available, using git rev-parse HEAD"
    CI_COMMIT_SHA=$(git rev-parse HEAD)
    if [ $? -ne 0 ]; then
        echo "Error: Failed to get commit SHA"
        exit 1
    fi
fi

# Login to registry
if ! docker login -u gitlab-ci-token -p $CCPP_ACCESS_TOKEN $IMAGE_REGISTRY; then
    echo "Error: Failed to login to Docker registry"
    exit 1
fi

# Build Docker image directly (CI environment)
echo "Building Docker image with tag: $INCREMENTED_VERSION"
if [ ! -f Dockerfile ]; then
    echo "Error: Dockerfile not found"
    exit 1
fi

if [ -z "$CCPP_ACCESS_TOKEN" ]; then
    echo "Error: CCPP_ACCESS_TOKEN not available for Docker build"
    exit 1
fi

if ! time docker build -f Dockerfile --build-arg GITLAB_PASSWORD=$CCPP_ACCESS_TOKEN -t api-assistant:$INCREMENTED_VERSION .; then
    echo "Error: Docker build failed"
    exit 1
fi
echo "✅ Production image built successfully with tag: $INCREMENTED_VERSION"

# Define image names and tag for registry
LOCAL_IMAGE_NAME="api-assistant:$INCREMENTED_VERSION"
DOCKER_IMAGE_SHA=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
DOCKER_IMAGE_SEMVER=$CI_REGISTRY_IMAGE:$INCREMENTED_VERSION

# Tag the locally built image with registry names
if ! docker tag $LOCAL_IMAGE_NAME $DOCKER_IMAGE_SHA; then
    echo "Error: Failed to tag image with SHA"
    exit 1
fi
if ! docker tag $LOCAL_IMAGE_NAME $DOCKER_IMAGE_SEMVER; then
    echo "Error: Failed to tag image with semantic version"
    exit 1
fi

# Push images to registry
if ! docker push $DOCKER_IMAGE_SHA; then
    echo "Error: Failed to push SHA-tagged image"
    exit 1
fi
if ! docker push $DOCKER_IMAGE_SEMVER; then
    echo "Error: Failed to push semantic version-tagged image"
    exit 1
fi

# Validate image was pushed successfully
if ! docker pull $DOCKER_IMAGE_SEMVER >/dev/null 2>&1; then
    echo "Error: Failed to validate pushed image - image not accessible"
    exit 1
fi
echo "Container registry updated successfully" 