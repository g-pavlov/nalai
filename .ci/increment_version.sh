#!/bin/bash

# Version Increment Script for GitLab CI
# =====================================
# This script handles semantic versioning and tag creation

set -e

echo "Checking for version management..."

# Validate required environment variables with merge request context support
if [ -z "$CI_DEFAULT_BRANCH" ]; then
    echo "Error: Required CI environment variable CI_DEFAULT_BRANCH is missing"
    exit 1
fi

# In merge request context, CI_COMMIT_BRANCH is not set, use CI_MERGE_REQUEST_SOURCE_BRANCH_NAME
if [ -z "$CI_COMMIT_BRANCH" ] && [ -z "$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME" ]; then
    echo "Error: Required CI environment variables are missing"
    echo "CI_COMMIT_BRANCH: $CI_COMMIT_BRANCH"
    echo "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME: $CI_MERGE_REQUEST_SOURCE_BRANCH_NAME"
    exit 1
fi

# Simple version comparison function
compare_versions() {
    local version1=$1
    local version2=$2
    
    IFS='.' read -r -a v1_parts <<< "$version1"
    IFS='.' read -r -a v2_parts <<< "$version2"
    
    for i in {0..2}; do
        if [ "${v1_parts[$i]}" -gt "${v2_parts[$i]}" ]; then
            echo "greater"
            return 0
        elif [ "${v1_parts[$i]}" -lt "${v2_parts[$i]}" ]; then
            echo "less"
            return 0
        fi
    done
    echo "equal"
}

# Use version utilities for version management
echo "Using version utilities for version management..."

# Always fetch latest tags from remote first
echo "Fetching latest tags from remote repository..."
git fetch --tags --quiet || echo "Warning: Failed to fetch tags from remote"

# Get main branch baseline for auto-increment and conflict detection
MAIN_BASELINE=$(git tag --sort=-version:refname --merged origin/main | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | head -n1)
if [ -z "$MAIN_BASELINE" ]; then
    MAIN_BASELINE="0.0.0"
fi
echo "Main branch baseline version: $MAIN_BASELINE"

# Check if we have any semantic version tags (including remote)
CURRENT_VERSION=$(git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | head -n1)
if [ -n "$CURRENT_VERSION" ]; then
    echo "Semantic version tags found, checking for manual version bumps..."
    echo "Current latest version: $CURRENT_VERSION"
    
    # Check if there are any newer manual version tags on this branch
    # This handles the case where a feature branch has manual version bumps
    NEWER_TAGS=$(git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | head -n5)
    
    # Find the highest version tag that's newer than current
    HIGHEST_VERSION=""
    for tag in $NEWER_TAGS; do
        if [ "$(compare_versions "$tag" "$CURRENT_VERSION")" = "greater" ]; then
            HIGHEST_VERSION="$tag"
            break
        fi
    done
    
    if [ -n "$HIGHEST_VERSION" ]; then
        # Check for backward targeting (manual version < main baseline)
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        source "$SCRIPT_DIR/version_utils.sh"
        if detect_backward_targeting "$HIGHEST_VERSION" "$MAIN_BASELINE"; then
            generate_backward_targeting_message "$HIGHEST_VERSION" "$MAIN_BASELINE" "$(git rev-parse --short HEAD)"
            exit 1
        fi
        
        echo "Found valid manual version tag: $HIGHEST_VERSION (manual version wins)"
        INCREMENTED_VERSION="$HIGHEST_VERSION"
    else
        echo "No manual version tags found, auto-incrementing patch version from main baseline..."
        # Auto-increment from main baseline only (ignore feature branch tags)
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        source "$SCRIPT_DIR/version_utils.sh"
        INCREMENTED_VERSION=$(increment_patch_version "$MAIN_BASELINE")
        # Create the tag
        git tag "$INCREMENTED_VERSION"
        echo "Created patch version tag: $INCREMENTED_VERSION"
    fi
else
    echo "No semantic version tags found, creating initial version..."
    # Check if 0.1.0 already exists remotely
    if git ls-remote --tags origin | grep -q "refs/tags/0.1.0"; then
        echo "Warning: Tag 0.1.0 already exists remotely, using it..."
        INCREMENTED_VERSION="0.1.0"
    else
        # Create initial version tag
        git tag "0.1.0"
        echo "Created initial version tag: 0.1.0"
        INCREMENTED_VERSION="0.1.0"
    fi
fi

# Validate final version
if [[ -z "$INCREMENTED_VERSION" ]] || [[ ! "$INCREMENTED_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Invalid final version: $INCREMENTED_VERSION"
    exit 1
fi

# Export version for other jobs
echo "Creating build.env file with INCREMENTED_VERSION=$INCREMENTED_VERSION"
echo "INCREMENTED_VERSION=$INCREMENTED_VERSION" > build.env

# Create and push tag transparently
echo "Creating and pushing version tag: $INCREMENTED_VERSION"

if ! git config user.email "${GITLAB_USER_EMAIL}"; then
    echo "Error: Failed to set git user email"
    exit 1
fi
if ! git config user.name "${GITLAB_USER_LOGIN}"; then
    echo "Error: Failed to set git user name"
    exit 1
fi

# Push tag to remote using CCPP_ACCESS_TOKEN (injected by GitLab environment)
PUSH_URL="https://gitlab-ci-token:${CCPP_ACCESS_TOKEN}@${CI_PROJECT_URL#https://}"

if ! git push "$PUSH_URL" "$INCREMENTED_VERSION"; then
    echo "Error: Failed to push git tag to remote"
    echo "Tag $INCREMENTED_VERSION was created locally but not pushed"
    exit 1
else
    echo "Successfully created and pushed version tag: $INCREMENTED_VERSION"
fi 