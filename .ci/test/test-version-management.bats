#!/usr/bin/env bats

# BATS Test Suite for Version Management Strategy
# ===============================================
# This suite tests the version management strategy including:
# - Backward targeting detection
# - Main branch baseline logic
# - Manual version validation
# - Auto-increment behavior
# - Error message generation

setup() {
    # Setup function runs before each test
    export PROJECT_ROOT="$(cd ../../.. && pwd)"
    export CI_SCRIPTS_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")" && pwd)/.."
    
    # Create temporary directory for each test
    export TEST_TMPDIR=$(mktemp -d)
    
    # Source version utilities for testing
    source "$CI_SCRIPTS_DIR/version_utils.sh"
}

teardown() {
    # Cleanup function runs after each test
    rm -rf "$TEST_TMPDIR"
    unset TEST_TMPDIR
}

# ==================================================
# Version Utility Function Tests
# ==================================================

@test "detect_backward_targeting function exists" {
    run type detect_backward_targeting
    [ "$status" -eq 0 ]
}

@test "generate_backward_targeting_message function exists" {
    run type generate_backward_targeting_message
    [ "$status" -eq 0 ]
}

@test "increment_patch_version function exists" {
    run type increment_patch_version
    [ "$status" -eq 0 ]
}

@test "increment_minor_version function exists" {
    run type increment_minor_version
    [ "$status" -eq 0 ]
}

@test "increment_major_version function exists" {
    run type increment_major_version
    [ "$status" -eq 0 ]
}

# ==================================================
# Backward Targeting Detection Tests
# ==================================================

@test "detect_backward_targeting - detects stale version (0.9.1 < 0.10.0)" {
    run detect_backward_targeting "0.9.1" "0.10.0"
    [ "$status" -eq 0 ]  # Function returns 0 (true) for backward targeting
}

@test "detect_backward_targeting - allows valid version (1.1.0 > 1.0.0)" {
    run detect_backward_targeting "1.1.0" "1.0.0"
    [ "$status" -eq 1 ]  # Function returns 1 (false) for valid version
}

@test "detect_backward_targeting - allows equal version (1.0.0 = 1.0.0)" {
    run detect_backward_targeting "1.0.0" "1.0.0"
    [ "$status" -eq 1 ]  # Function returns 1 (false) for equal version
}

@test "detect_backward_targeting - allows newer patch (1.0.1 > 1.0.0)" {
    run detect_backward_targeting "1.0.1" "1.0.0"
    [ "$status" -eq 1 ]  # Function returns 1 (false) for valid version
}

@test "detect_backward_targeting - allows newer minor (1.1.0 > 1.0.0)" {
    run detect_backward_targeting "1.1.0" "1.0.0"
    [ "$status" -eq 1 ]  # Function returns 1 (false) for valid version
}

@test "detect_backward_targeting - allows newer major (2.0.0 > 1.0.0)" {
    run detect_backward_targeting "2.0.0" "1.0.0"
    [ "$status" -eq 1 ]  # Function returns 1 (false) for valid version
}

# ==================================================
# Version Increment Tests
# ==================================================

@test "increment_patch_version - basic increment (1.0.0 → 1.0.1)" {
    run increment_patch_version "1.0.0"
    [ "$status" -eq 0 ]
    [ "$output" = "1.0.1" ]
}

@test "increment_patch_version - patch increment (0.9.1 → 0.9.2)" {
    run increment_patch_version "0.9.1"
    [ "$status" -eq 0 ]
    [ "$output" = "0.9.2" ]
}

@test "increment_patch_version - double digit patch (1.0.9 → 1.0.10)" {
    run increment_patch_version "1.0.9"
    [ "$status" -eq 0 ]
    [ "$output" = "1.0.10" ]
}

@test "increment_minor_version - basic increment (1.0.0 → 1.1.0)" {
    run increment_minor_version "1.0.0"
    [ "$status" -eq 0 ]
    [ "$output" = "1.1.0" ]
}

@test "increment_minor_version - minor increment (0.9.1 → 0.10.0)" {
    run increment_minor_version "0.9.1"
    [ "$status" -eq 0 ]
    [ "$output" = "0.10.0" ]
}

@test "increment_minor_version - double digit minor (1.9.0 → 1.10.0)" {
    run increment_minor_version "1.9.0"
    [ "$status" -eq 0 ]
    [ "$output" = "1.10.0" ]
}

@test "increment_major_version - basic increment (1.0.0 → 2.0.0)" {
    run increment_major_version "1.0.0"
    [ "$status" -eq 0 ]
    [ "$output" = "2.0.0" ]
}

@test "increment_major_version - major increment (0.9.1 → 1.0.0)" {
    run increment_major_version "0.9.1"
    [ "$status" -eq 0 ]
    [ "$output" = "1.0.0" ]
}

@test "increment_major_version - double digit major (9.0.0 → 10.0.0)" {
    run increment_major_version "9.0.0"
    [ "$status" -eq 0 ]
    [ "$output" = "10.0.0" ]
}

# ==================================================
# Error Message Generation Tests
# ==================================================

@test "generate_backward_targeting_message - produces correct output" {
    run generate_backward_targeting_message "0.9.1" "0.10.0" "test-context"
    [ "$status" -eq 0 ]
    [[ "$output" == *"BACKWARD TARGETING DETECTED"* ]]
    [[ "$output" == *"Feature branch manual version: 0.9.1"* ]]
    [[ "$output" == *"Main branch baseline version: 0.10.0"* ]]
    [[ "$output" == *"timeline mismatch"* ]]
}

@test "generate_backward_targeting_message - includes patch suggestion" {
    run generate_backward_targeting_message "0.9.1" "0.10.0" "test-context"
    [ "$status" -eq 0 ]
    [[ "$output" == *"0.10.1"* ]]  # Should suggest patch increment
}

@test "generate_backward_targeting_message - includes minor suggestion" {
    run generate_backward_targeting_message "0.9.1" "0.10.0" "test-context"
    [ "$status" -eq 0 ]
    [[ "$output" == *"0.11.0"* ]]  # Should suggest minor increment
}

@test "generate_backward_targeting_message - includes major suggestion" {
    run generate_backward_targeting_message "0.9.1" "0.10.0" "test-context"
    [ "$status" -eq 0 ]
    [[ "$output" == *"1.0.0"* ]]   # Should suggest major increment
}

@test "generate_backward_targeting_message - includes resolution instructions" {
    run generate_backward_targeting_message "0.9.1" "0.10.0" "test-context"
    [ "$status" -eq 0 ]
    [[ "$output" == *"git tag -d 0.9.1"* ]]
    [[ "$output" == *"git push origin --tags"* ]]
}

@test "generate_backward_targeting_message - includes context" {
    run generate_backward_targeting_message "0.9.1" "0.10.0" "MR-123"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Context: MR-123"* ]]
}

# ==================================================
# Integration Scenario Tests
# ==================================================

@test "integration - happy path with manual version" {
    # Test: Feature branch with valid manual version merges successfully
    # Main baseline: 1.0.0
    # Manual version: 1.1.0 (valid - newer than main)
    run detect_backward_targeting "1.1.0" "1.0.0"
    [ "$status" -eq 1 ]  # Should NOT be backward targeting
}

@test "integration - happy path with auto-increment" {
    # Test: Feature branch without manual version gets auto-incremented from main
    # Main baseline: 1.0.0
    # Auto-increment should be: 1.0.1
    run increment_patch_version "1.0.0"
    [ "$status" -eq 0 ]
    [ "$output" = "1.0.1" ]
}

@test "integration - backward targeting blocked" {
    # Test: Feature branch with stale manual version is blocked
    # Main baseline: 0.10.0
    # Manual version: 0.9.1 (stale - older than main)
    run detect_backward_targeting "0.9.1" "0.10.0"
    [ "$status" -eq 0 ]  # Should be detected as backward targeting
}

@test "integration - main branch only auto-increment" {
    # Test: Auto-increment ignores feature branch tags, uses only main branch
    # Even if there are higher feature branch tags, auto-increment should use main baseline
    run increment_patch_version "0.10.0"
    [ "$status" -eq 0 ]
    [ "$output" = "0.10.1" ]
}

# ==================================================
# Edge Case Tests
# ==================================================

@test "edge case - zero versions" {
    run detect_backward_targeting "0.0.0" "0.0.0"
    [ "$status" -eq 1 ]  # Equal versions should not be backward targeting
}

@test "edge case - very large version numbers" {
    run detect_backward_targeting "999.999.999" "1000.0.0"
    [ "$status" -eq 0 ]  # Should be detected as backward targeting
}

@test "edge case - single digit components" {
    run increment_patch_version "1.0.0"
    [ "$status" -eq 0 ]
    [ "$output" = "1.0.1" ]
}

@test "edge case - double digit components" {
    run increment_patch_version "1.0.99"
    [ "$status" -eq 0 ]
    [ "$output" = "1.0.100" ]
}

# ==================================================
# CI Script Integration Tests
# ==================================================

@test "CI script - backward targeting detection logic exists" {
    # Test that backward targeting detection is implemented in increment_version.sh
    run grep -q "detect_backward_targeting" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
}

@test "CI script - backward targeting blocks merge" {
    # Test that backward targeting calls exit 1
    run grep -A5 -B5 "detect_backward_targeting" "$CI_SCRIPTS_DIR/increment_version.sh" | grep -q "exit 1"
    [ "$status" -eq 0 ]
}

@test "CI script - backward targeting generates error message" {
    # Test that backward targeting calls generate_backward_targeting_message
    run grep -q "generate_backward_targeting_message" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
}

@test "CI script - main baseline detection logic exists" {
    # Test that main baseline detection is implemented
    run grep -q "MAIN_BASELINE=" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
}

@test "CI script - uses main branch baseline for auto-increment" {
    # Test that the script uses main branch tags only for auto-increment
    run grep -q "MAIN_BASELINE.*--merged origin/main" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
}

@test "CI script - auto-increment uses main baseline" {
    # Test that auto-increment calls increment_patch_version with MAIN_BASELINE
    run grep -q "increment_patch_version.*MAIN_BASELINE" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
}

@test "CI script - validates manual versions against main baseline" {
    # Test that manual versions are checked against main baseline
    run grep -A3 -B3 "detect_backward_targeting.*HIGHEST_VERSION.*MAIN_BASELINE" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
}

@test "CI script - allows valid manual versions" {
    # Test that valid manual versions (>= main baseline) are accepted
    run grep -A2 -B2 "Found valid manual version tag" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
}

# Rename duplicate test names to avoid BATS conflict
@test "Version management: CI environment - script integration points" {
    # Test that scripts use the CI variables defined in .gitlab-ci.yml
    run grep -r "INCREMENTED_VERSION" "$CI_SCRIPTS_DIR/"
    [ "$status" -eq 0 ]
    
    run grep -r "CI_REGISTRY_IMAGE" "$CI_SCRIPTS_DIR/"
    [ "$status" -eq 0 ]
    
    run grep -r "CI_PROJECT_NAMESPACE" "$CI_SCRIPTS_DIR/"
    [ "$status" -eq 0 ]
}

@test "Version management: CI artifacts - build.env file integration" {
    # Test that build.env is created and consumed correctly
    run grep -q "build.env" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
    
    run grep -q "build.env" "$CI_SCRIPTS_DIR/create_and_push_image.sh"
    [ "$status" -eq 0 ]
} 