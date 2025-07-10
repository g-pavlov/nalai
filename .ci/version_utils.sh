#!/bin/bash

# Version Management Utilities
# ============================
# This script provides version incrementing functions for semantic versioning
# Used by both Makefile and GitLab CI pipeline

set -e

# Function to increment patch version (1.0.0 → 1.0.1)
increment_patch_version() {
    local version=$1
    IFS='.' read -r -a version_parts <<< "$version"
    ((version_parts[2]++))
    echo "${version_parts[0]}.${version_parts[1]}.${version_parts[2]}"
}

# Function to increment minor version (1.0.0 → 1.1.0)
increment_minor_version() {
    local version=$1
    IFS='.' read -r -a version_parts <<< "$version"
    ((version_parts[1]++))
    version_parts[2]=0  # Reset patch to 0
    echo "${version_parts[0]}.${version_parts[1]}.${version_parts[2]}"
}

# Function to increment major version (1.0.0 → 2.0.0)
increment_major_version() {
    local version=$1
    IFS='.' read -r -a version_parts <<< "$version"
    ((version_parts[0]++))
    version_parts[1]=0  # Reset minor to 0
    version_parts[2]=0  # Reset patch to 0
    echo "${version_parts[0]}.${version_parts[1]}.${version_parts[2]}"
}

# Function to get the latest git tag
get_latest_tag() {
    # Always fetch tags from remote to ensure we have the latest state
    if ! git fetch --tags --quiet; then
        echo "Warning: Failed to fetch tags from remote repository, using local tags only." >&2
    fi
    
    # Get the latest semantic version tag (both local and remote)
    local latest_tag=$(git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | head -n1)
    
    if [ -z "$latest_tag" ]; then
        # If no local tags, check remote tags
        latest_tag=$(git ls-remote --tags origin | grep -E 'refs/tags/[0-9]+\.[0-9]+\.[0-9]+$' | sed 's|.*refs/tags/||' | sort -V | tail -n1)
    fi
    
    echo "$latest_tag"
}

# Function to get or create initial version
get_or_create_version() {
    local latest_tag=$(get_latest_tag)
    
    if [ -z "$latest_tag" ]; then
        echo "0.1.0"
    else
        echo "$latest_tag"
    fi
}

# Function to check if a version tag already exists
version_exists() {
    local version=$1
    
    # Check local tags first
    if git tag --list | grep -q "^${version}$"; then
        return 0  # Tag exists locally
    fi
    
    # Check remote tags
    if git ls-remote --tags origin | grep -q "refs/tags/${version}$"; then
        return 0  # Tag exists remotely
    fi
    
    return 1  # Tag doesn't exist
}

# Function to compare semantic versions
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

# Function to detect backward targeting conflicts
detect_backward_targeting() {
    local manual_version=$1
    local main_baseline=$2
    
    # If manual version is less than main baseline, we have backward targeting
    local comparison=$(compare_versions "$manual_version" "$main_baseline")
    
    if [ "$comparison" = "less" ]; then
        return 0  # Backward targeting detected
    fi
    
    return 1  # No backward targeting
}

# Function to generate backward targeting resolution message
generate_backward_targeting_message() {
    local manual_version=$1
    local main_baseline=$2
    local context=${3:-$(get_merge_request_info)}
    
    echo "🚨 BACKWARD TARGETING DETECTED" >&2
    echo "=====================================" >&2
    echo "Feature branch manual version: $manual_version" >&2
    echo "Main branch baseline version: $main_baseline" >&2
    echo "Context: $context" >&2
    echo "" >&2
    echo "This would create a timeline mismatch where $manual_version appears after $main_baseline." >&2
    echo "" >&2
    echo "This requires manual resolution to determine the correct semantic version:" >&2
    echo "1. Patch to current main: $(increment_patch_version "$main_baseline")" >&2
    echo "2. Minor increment: $(increment_minor_version "$main_baseline")" >&2
    echo "3. Major increment: $(increment_major_version "$main_baseline")" >&2
    echo "" >&2
    echo "To resolve:" >&2
    echo "1. Update your feature branch version tag:" >&2
    echo "   git tag -d $manual_version" >&2
    echo "   git tag <appropriate_version>" >&2
    echo "   git push origin --tags" >&2
    echo "2. Re-run this pipeline" >&2
    echo "" >&2
    echo "Consider the semantic scope of your changes relative to the current main branch." >&2
}

# Function to detect semantic conflicts that require human intervention
detect_semantic_conflict() {
    local target_version=$1
    local increment_type=$2
    local current_latest=$(get_or_create_version)
    
    # If target version is less than or equal to current latest, we have a conflict
    local comparison=$(compare_versions "$target_version" "$current_latest")
    
    if [ "$comparison" = "less" ] || [ "$comparison" = "equal" ]; then
        return 0  # Conflict detected
    fi
    
    # If target version exists, we have a conflict
    if version_exists "$target_version"; then
        return 0  # Conflict detected
    fi
    
    return 1  # No conflict
}

# Function to check if conflict is auto-resolvable (same semantic level)
is_auto_resolvable_conflict() {
    local target_version=$1
    local increment_type=$2
    local current_latest=$(get_or_create_version)
    
    # If target version is less than current latest, check if it's the same level
    local comparison=$(compare_versions "$target_version" "$current_latest")
    
    if [ "$comparison" = "less" ]; then
        # Check if both versions are at the same semantic level
        IFS='.' read -r -a target_parts <<< "$target_version"
        IFS='.' read -r -a current_parts <<< "$current_latest"
        
        # For patch conflicts: major and minor should be the same
        if [ "$increment_type" = "patch" ]; then
            if [ "${target_parts[0]}" = "${current_parts[0]}" ] && [ "${target_parts[1]}" = "${current_parts[1]}" ]; then
                return 0  # Auto-resolvable
            fi
        fi
        
        # For minor conflicts: major should be the same, minor should be different
        if [ "$increment_type" = "minor" ]; then
            if [ "${target_parts[0]}" = "${current_parts[0]}" ]; then
                return 0  # Auto-resolvable
            fi
        fi
        
        # For major conflicts: always require manual intervention (conservative approach)
        if [ "$increment_type" = "major" ]; then
            return 1  # Not auto-resolvable - require manual intervention
        fi
    fi
    
    # If target version exists, check if it's auto-resolvable
    if version_exists "$target_version"; then
        IFS='.' read -r -a target_parts <<< "$target_version"
        IFS='.' read -r -a current_parts <<< "$current_latest"
        
        # For patch conflicts: major and minor should be the same
        if [ "$increment_type" = "patch" ]; then
            if [ "${target_parts[0]}" = "${current_parts[0]}" ] && [ "${target_parts[1]}" = "${current_parts[1]}" ]; then
                return 0  # Auto-resolvable
            fi
        fi
        
        # For minor conflicts: major should be the same
        if [ "$increment_type" = "minor" ]; then
            if [ "${target_parts[0]}" = "${current_parts[0]}" ]; then
                return 0  # Auto-resolvable
            fi
        fi
        
        # For major conflicts: always require manual intervention
        if [ "$increment_type" = "major" ]; then
            return 1  # Not auto-resolvable
        fi
    fi
    
    return 1  # Not auto-resolvable
}

# Function to auto-resolve same-level conflicts
auto_resolve_conflict() {
    local target_version=$1
    local increment_type=$2
    local current_latest=$(get_or_create_version)
    
    echo "Auto-resolving same-level conflict:" >&2
    echo "  Target version: $target_version" >&2
    echo "  Current latest: $current_latest" >&2
    echo "  Increment type: $increment_type" >&2
    
    case $increment_type in
        "patch")
            echo $(increment_patch_version "$current_latest")
            ;;
        "minor")
            echo $(increment_minor_version "$current_latest")
            ;;
        "major")
            echo $(increment_major_version "$current_latest")
            ;;
        *)
            echo "Error: Invalid increment type. Use 'patch', 'minor', or 'major'" >&2
            return 1
            ;;
    esac
}

# Function to generate conflict resolution message
generate_conflict_message() {
    local target_version=$1
    local increment_type=$2
    local current_latest=$(get_or_create_version)
    local context=${3:-$(get_merge_request_info)}
    
    echo "🚨 SEMANTIC VERSION CONFLICT DETECTED" >&2
    echo "=====================================" >&2
    echo "Current latest version: $current_latest" >&2
    echo "Target version: $target_version ($increment_type increment)" >&2
    echo "Context: $context" >&2
    echo "" >&2
    echo "This conflict requires human intervention to determine the correct version." >&2
    echo "" >&2
    echo "Possible resolutions:" >&2
    
    case $increment_type in
        "patch")
            echo "1. Use patch increment: $(increment_patch_version "$current_latest")" >&2
            echo "2. Use minor increment: $(increment_minor_version "$current_latest")" >&2
            echo "3. Use major increment: $(increment_major_version "$current_latest")" >&2
            ;;
        "minor")
            echo "1. Use minor increment: $(increment_minor_version "$current_latest")" >&2
            echo "2. Use major increment: $(increment_major_version "$current_latest")" >&2
            ;;
        "major")
            echo "1. Use major increment: $(increment_major_version "$current_latest")" >&2
            ;;
    esac
    
    echo "" >&2
    echo "To resolve:" >&2
    echo "1. Create the appropriate version tag manually" >&2
    echo "2. Re-run this pipeline" >&2
    echo "" >&2
    echo "Example: git tag $(increment_patch_version "$current_latest") && git push origin $(increment_patch_version "$current_latest")" >&2
}

# Function to get merge request info for versioning context
get_merge_request_info() {
    if [ -n "$CI_MERGE_REQUEST_ID" ]; then
        echo "MR-$CI_MERGE_REQUEST_ID"
    elif [ -n "$CI_COMMIT_REF_NAME" ]; then
        echo "BRANCH-${CI_COMMIT_REF_NAME//[^a-zA-Z0-9]/}"
    else
        echo "COMMIT-$(git rev-parse --short HEAD)"
    fi
}

# Main function to increment version with conflict detection
increment_version_with_conflict_detection() {
    local increment_type=$1
    local context=${2:-$(get_merge_request_info)}
    
    local current_version=$(get_or_create_version)
    echo "Current version: $current_version" >&2
    
    case $increment_type in
        "patch")
            local target_version=$(increment_patch_version "$current_version")
            ;;
        "minor")
            local target_version=$(increment_minor_version "$current_version")
            ;;
        "major")
            local target_version=$(increment_major_version "$current_version")
            ;;
        *)
            echo "Error: Invalid increment type. Use 'patch', 'minor', or 'major'" >&2
            exit 1
            ;;
    esac
    
    echo "Target version: $target_version" >&2
    
    # Check for semantic conflicts
    if detect_semantic_conflict "$target_version" "$increment_type"; then
        # Check if conflict is auto-resolvable
        if is_auto_resolvable_conflict "$target_version" "$increment_type"; then
            local final_version=$(auto_resolve_conflict "$target_version" "$increment_type")
            echo "Auto-resolved to: $final_version" >&2
            echo "$final_version"
        else
            generate_conflict_message "$target_version" "$increment_type" "$context"
            echo "Error: Semantic version conflict detected. Manual intervention required." >&2
            exit 1
        fi
    else
        echo "New version: $target_version" >&2
        echo "$target_version"
    fi
}

# Main function to increment version based on type (backward compatibility)
increment_version() {
    increment_version_with_conflict_detection "$1"
}

# If script is run directly, use the first argument as increment type
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -eq 0 ]; then
        echo "Usage: $0 {patch|minor|major} [context]"
        exit 1
    fi
    increment_version_with_conflict_detection "$1" "${2:-}"
fi 