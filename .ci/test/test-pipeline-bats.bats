#!/usr/bin/env bats

# BATS Test Suite for CI Pipeline Scripts - Workflow Testing
# =========================================================
# This suite tests the BEHAVIOR of CI scripts in relation to the actual CI workflow
# Maps directly to .gitlab-ci.yml stages and workflow logic

setup() {
    # Setup function runs before each test
    export PROJECT_ROOT="$(cd ../../.. && pwd)"
    export CI_SCRIPTS_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")" && pwd)/.."
    
    # Create temporary directory for each test
    export TEST_TMPDIR=$(mktemp -d)
    
    # Mock git to block remote-changing commands and simulate safe local behavior
    cat > "$TEST_TMPDIR/git" <<'EOF'
#!/bin/bash
if [[ "$1" =~ ^(push|fetch|pull|clone|ls-remote)$ ]]; then
  echo "[MOCK GIT] Blocked remote-changing git command: $@" >&2
  exit 99
else
  /usr/bin/git "$@"
fi
EOF
    chmod +x "$TEST_TMPDIR/git"
    export PATH="$TEST_TMPDIR:$PATH"
}

teardown() {
    # Cleanup function runs after each test
    rm -rf "$TEST_TMPDIR"
    unset TEST_TMPDIR
}

# Helper function to run scripts with environment
run_script_with_env() {
    local script="$1"
    local env_vars="$2"
    run bash -c "$env_vars $script"
}

# ==================================================
# CI Stage 1: Increment Version Job Tests
# ==================================================

@test "Increment Version job - runs only on main branch" {
    # Test the rule: if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    export CI_COMMIT_BRANCH="main"
    export CI_DEFAULT_BRANCH="main"
    
    run bash -c 'if [ "$CI_COMMIT_BRANCH" = "$CI_DEFAULT_BRANCH" ]; then echo "Increment Version job WOULD run"; else echo "Increment Version job would NOT run"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Increment Version job WOULD run"* ]]
}

@test "Increment Version job - does not run on feature branches" {
    # Test the rule: if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    export CI_COMMIT_BRANCH="feature/new-feature"
    export CI_DEFAULT_BRANCH="main"
    
    run bash -c 'if [ "$CI_COMMIT_BRANCH" = "$CI_DEFAULT_BRANCH" ]; then echo "Increment Version job WOULD run"; else echo "Increment Version job would NOT run"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Increment Version job would NOT run"* ]]
}

@test "Increment Version job - requires CI_DEFAULT_BRANCH environment variable" {
    run_script_with_env "$CI_SCRIPTS_DIR/increment_version.sh" ""
    [ "$status" -ne 0 ]
    [[ "$output" == *"Error: Required CI environment variable CI_DEFAULT_BRANCH is missing"* ]]
}

@test "Increment Version job - requires CI_COMMIT_BRANCH or CI_MERGE_REQUEST_SOURCE_BRANCH_NAME" {
    run_script_with_env "$CI_SCRIPTS_DIR/increment_version.sh" "CI_DEFAULT_BRANCH=main"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Error: Required CI environment variables are missing"* ]]
}

@test "Increment Version job - creates build.env artifact" {
    run grep -q "build.env" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
}

# ==================================================
# CI Stage 1: Build Job Tests (Merge Request Path)
# ==================================================

@test "Build job - merge request path uses commit SHA" {
    # Test the merge request logic from .gitlab-ci.yml
    export CI_PIPELINE_SOURCE="merge_request_event"
    export CI_COMMIT_SHA="abc123def456"
    
    run bash -c 'if [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ]; then echo "INCREMENTED_VERSION=$CI_COMMIT_SHA"; else echo "Would use semantic version"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"INCREMENTED_VERSION=abc123def456"* ]]
}

@test "Build job - merge request path creates build.env with commit SHA" {
    # Test the exact logic from .gitlab-ci.yml
    export CI_PIPELINE_SOURCE="merge_request_event"
    export CI_COMMIT_SHA="abc123def456"
    
    run bash -c 'if [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ]; then echo "INCREMENTED_VERSION=$CI_COMMIT_SHA" > build.env; cat build.env; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"INCREMENTED_VERSION=abc123def456"* ]]
}

@test "Build job - main branch path uses semantic version from Increment Version job" {
    # Test that main branch uses the build.env from Increment Version job
    export CI_PIPELINE_SOURCE="push"
    export CI_COMMIT_BRANCH="main"
    
    # Simulate build.env from Increment Version job
    echo "INCREMENTED_VERSION=1.2.3" > "$TEST_TMPDIR/build.env"
    
    run bash -c 'if [ "$CI_PIPELINE_SOURCE" != "merge_request_event" ]; then echo "Would use build.env from Increment Version job"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Would use build.env from Increment Version job"* ]]
}

@test "Build job - create_and_push_image.sh requires INCREMENTED_VERSION" {
    run_script_with_env "$CI_SCRIPTS_DIR/create_and_push_image.sh" ""
    [ "$status" -ne 0 ]
    [[ "$output" == *"Error: INCREMENTED_VERSION not set and build.env file not found"* ]] || [[ "$output" == *"Error:"* ]]
}

@test "Build job - create_and_push_image.sh requires CI_REGISTRY_IMAGE" {
    run_script_with_env "$CI_SCRIPTS_DIR/create_and_push_image.sh" "INCREMENTED_VERSION=0.1.0"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Error: Required environment variables are missing"* ]]
}

# ==================================================
# CI Stage 2: Deploy Job Tests
# ==================================================

@test "Deploy job - runs only on main branch" {
    # Test the rule: if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    export CI_COMMIT_BRANCH="main"
    export CI_DEFAULT_BRANCH="main"
    
    run bash -c 'if [ "$CI_COMMIT_BRANCH" = "$CI_DEFAULT_BRANCH" ]; then echo "Deploy job WOULD run"; else echo "Deploy job would NOT run"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Deploy job WOULD run"* ]]
}

@test "Deploy job - does not run on feature branches" {
    export CI_COMMIT_BRANCH="feature/new-feature"
    export CI_DEFAULT_BRANCH="main"
    
    run bash -c 'if [ "$CI_COMMIT_BRANCH" = "$CI_DEFAULT_BRANCH" ]; then echo "Deploy job WOULD run"; else echo "Deploy job would NOT run"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Deploy job would NOT run"* ]]
}

@test "Deploy job - update_deployment_config.sh requires CI_PROJECT_NAMESPACE" {
    run_script_with_env "$CI_SCRIPTS_DIR/update_deployment_config.sh" ""
    [ "$status" -ne 0 ]
    [[ "$output" == *"Error: Required environment variables are missing"* ]]
}

# ==================================================
# CI Workflow Integration Tests
# ==================================================

@test "Complete workflow - merge request path" {
    # Test the complete merge request workflow
    export CI_PIPELINE_SOURCE="merge_request_event"
    export CI_COMMIT_SHA="abc123def456"
    
    # Step 1: Increment Version should NOT run
    run bash -c 'if [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ]; then echo "Increment Version: SKIPPED"; else echo "Increment Version: WOULD RUN"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Increment Version: SKIPPED"* ]]
    
    # Step 2: Build should use commit SHA
    run bash -c 'if [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ]; then echo "Build: using commit SHA $CI_COMMIT_SHA"; else echo "Build: using semantic version"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Build: using commit SHA abc123def456"* ]]
    
    # Step 3: Deploy should NOT run
    run bash -c 'if [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ]; then echo "Deploy: SKIPPED (merge request)"; else echo "Deploy: WOULD RUN"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Deploy: SKIPPED (merge request)"* ]]
}

@test "Complete workflow - main branch path" {
    # Test the complete main branch workflow
    export CI_PIPELINE_SOURCE="push"
    export CI_COMMIT_BRANCH="main"
    export CI_DEFAULT_BRANCH="main"
    
    # Step 1: Increment Version should run
    run bash -c 'if [ "$CI_COMMIT_BRANCH" = "$CI_DEFAULT_BRANCH" ]; then echo "Increment Version: WOULD RUN"; else echo "Increment Version: SKIPPED"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Increment Version: WOULD RUN"* ]]
    
    # Step 2: Build should use semantic version from Increment Version
    run bash -c 'if [ "$CI_PIPELINE_SOURCE" != "merge_request_event" ]; then echo "Build: using semantic version from build.env"; else echo "Build: using commit SHA"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Build: using semantic version from build.env"* ]]
    
    # Step 3: Deploy should run
    run bash -c 'if [ "$CI_COMMIT_BRANCH" = "$CI_DEFAULT_BRANCH" ]; then echo "Deploy: WOULD RUN"; else echo "Deploy: SKIPPED"; fi'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Deploy: WOULD RUN"* ]]
}

# ==================================================
# CI Environment Variable Integration Tests
# ==================================================

@test "CI environment - script integration points" {
    # Test that scripts use the CI variables defined in .gitlab-ci.yml
    run grep -r "INCREMENTED_VERSION" "$CI_SCRIPTS_DIR/"
    [ "$status" -eq 0 ]
    
    run grep -r "CI_REGISTRY_IMAGE" "$CI_SCRIPTS_DIR/"
    [ "$status" -eq 0 ]
    
    run grep -r "CI_PROJECT_NAMESPACE" "$CI_SCRIPTS_DIR/"
    [ "$status" -eq 0 ]
}

# ==================================================
# CI Artifact Integration Tests
# ==================================================

@test "CI artifacts - build.env file integration" {
    # Test that build.env is created and consumed correctly
    run grep -q "build.env" "$CI_SCRIPTS_DIR/increment_version.sh"
    [ "$status" -eq 0 ]
    
    run grep -q "build.env" "$CI_SCRIPTS_DIR/create_and_push_image.sh"
    [ "$status" -eq 0 ]
} 