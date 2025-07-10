# Version Management Guide

## Overview

This project uses semantic versioning (SemVer) with automated CI/CD integration. The version management system supports both manual version bumps and automatic patch increments using git tags as the single source of truth.

## Semantic Versioning

**Format: MAJOR.MINOR.PATCH**

- **MAJOR** (1.0.0 → 2.0.0): Breaking/incompatible changes
- **MINOR** (1.0.0 → 1.1.0): New features, backward compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, backward compatible

## Version Management System
This version management system is based on Git tags as the single source of truth for versioning.

```
Automated (CI/CD):
├── Transparent init (if no tags)
├── Auto-increment patch (every build)
└── Transparent tag creation and pushing

Manual (Developer Control):
├── make bump-minor (new features)
├── make bump-major (breaking changes)
└── make version (check current)
```

## Developer Workflows

### Bug Fix Workflow
```bash
# 1. Make your bug fix changes
git add .
git commit -m "Fix bug description"
git push

# 2. CI builds Docker image with commit SHA for testing
# Example: gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:82a3791bf4c8ba64942181b64043a8786aa4aa8b

# 3. When merged to main, CI automatically increments PATCH version
# Example: 1.0.0 → 1.0.1

# Final Docker images for main branch integrate commits:
# - gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:82a3791bf4c8ba64942181b64043a8786aa4aa8b
# - gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:1.0.1
```

### New Feature Workflow
```bash
# 1. Bump minor version for new features (on feature branch)
make bump-minor

# 2. Push code and tags together 
git add --all && git push origin feature-branch --tags

# 3. CI builds Docker image with commit SHA for testing
# Example: gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:82a3791bf4c8ba64942181b64043a8786aa4aa8b

# 4. When merging to main, CI detects your manual version and uses it (1.1.0)
# Note: Manual version tags are respected and override auto-increment

# Final Docker images for main branch integrate commits:
# - gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:82a3791bf4c8ba64942181b64043a8786aa4aa8b
# - gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:1.1.0
```

**Tip: Install automatic tag push hook**
```bash
# One-time setup
make install-version-hooks

# Then just push normally (tags are pushed automatically)
git add --all && git push origin feature-branch
```

### Breaking Change Workflow
```bash
# 1. Bump major version for breaking changes (on feature branch)
make bump-major

# 2. Push code and tags together (or omit the --tags if you have setup with make install-version-hooks)
git add --all && git push origin feature-branch --tags

# 3. CI builds Docker image with commit SHA for testing
# Example: gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:82a3791bf4c8ba64942181b64043a8786aa4aa8b

# 4. When merged to main, CI detects your manual version and uses it (2.0.0)
# Note: Manual version tags are respected and override auto-increment

# Final Docker images for main branch integrate commits:
# - gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:82a3791bf4c8ba64942181b64043a8786aa4aa8b
# - gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:2.0.0
```

**Tip: Install automatic tag push hook**
```bash
# One-time setup
make install-version-hooks

# Then just push normally (tags are pushed automatically)
git add --all && git push origin feature-branch
```


## Quick Reference

| Command | When to Use | Example |
|---------|-------------|---------|
| `make version` | See current version | `1.0.0` |
| `make init-version` | New project setup | Creates `0.1.0` |
| `make bump-minor` | New features | `1.0.0 → 1.1.0` |
| `make bump-major` | Breaking changes | `1.0.0 → 2.0.0` |
| `make install-version-hooks` | One-time setup | Enables automatic tag pushing (recommended) |



## CI/CD Behavior

### Transparent Initial Tag Initialization
- **When**: No semantic version tags exist
- **Action**: CI creates initial version tag automatically
- **Example**: No tags → CI creates `0.1.0`

### Automatic Version Increment and Tag Management
- **When**: Only on merge to main branch (not on merge requests)
- **Action**: CI automatically increments the appropriate version segment (PATCH, MINOR, or MAJOR) and creates/pushes the git tag
- **Examples**: 
  - Latest tag `1.0.0` → CI creates and pushes `1.0.1` (patch increment)
  - Latest tag `1.0.1` → CI creates and pushes `1.1.0` (minor increment) 
  - Latest tag `1.1.0` → CI creates and pushes `2.0.0` (major increment)
- **Exceptions**: 
  - Manual version bump exists (manual always wins)

### Docker Image Testing on Feature Branches
- **When**: On merge requests (feature branches)
- **Action**: CI builds and pushes Docker images with commit SHA for testing
- **Examples**:
  - `gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:82a3791bf4c8ba64942181b64043a8786aa4aa8b` (commit SHA)
- **Purpose**: Enable Docker image testing on feature branches without creating version tags

### Manual Version Respect
- **When**: Manual version bump detected on feature branch (newer tag exists)
- **Action**: CI uses the manually created version (**manual always overrides automatic**)
- **Example**: Manual tag `1.1.0` on feature branch → CI uses `1.1.0` when merged to main
- **Detection**: CI checks for newer version tags and uses the highest one

**Precedence Rules:**
| Manual Action | CI/CD Action | Result | Example |
|---------------|--------------|---------|---------
| `make bump-minor` on feature branch | Auto-increment patch | **Manual wins** | 1.0.0 → 1.1.0 (manual) |
| `make bump-major` on feature branch | Auto-increment patch | **Manual wins** | 1.0.0 → 2.0.0 (manual) |
| None | Auto-increment patch | **CI/CD wins** | 1.0.0 → 1.0.1 (automatic) |



### Semantic Version Conflict Resolution

The CI/CD pipeline includes intelligent conflict detection and resolution to handle concurrent version bumps and semantic conflicts.

#### Auto-Resolution Strategy

| **Conflict Type** | **Scenario** | **Auto-Resolve** | **Manual Required** | **Reasoning** |
|------------------|--------------|------------------|-------------------|---------------|
| **Patch vs Patch** | Both target `0.1.1` | ✅ `0.1.1` → `0.1.2` | ❌ | Sequential bug fixes preserve semantic meaning |
| **Minor vs Minor** | Both target `0.1.0` | ✅ `0.1.0` → `0.2.0` | ❌ | Sequential features preserve semantic meaning |
| **Major vs Major** | Both target `1.0.0` | ✅ `1.0.0` → `2.0.0` | ❌ | Sequential breaking changes preserve semantic meaning |
| **Patch vs Minor** | `0.1.1` vs `0.1.0` | ❌ | ✅ | Need to decide: `0.1.2` or `0.2.0` |
| **Minor vs Major** | `0.1.0` vs `1.0.0` | ❌ | ✅ | Need to decide: `0.2.0` or `2.0.0` |
| **Patch vs Major** | `0.1.1` vs `1.0.0` | ❌ | ✅ | Need to decide: `0.1.2` or `2.0.0` |
| **Backward Target** | Current `0.2.0`, target `0.1.1` | ❌ | ✅ | Target version < current version |
| **Version Exists** | Target `0.1.1` already exists | ❌ | ✅ | Exact version collision |



#### Decision Matrix

| **Current** | **Target** | **Type** | **Action** | **Result** |
|-------------|------------|----------|------------|------------|
| `0.1.0` | `0.1.1` | Patch | ✅ Auto-resolve | `0.1.1` |
| `0.1.0` | `0.1.1` | Patch (exists) | ✅ Auto-resolve | `0.1.2` |
| `0.0.1` | `0.1.0` | Minor | ✅ Auto-resolve | `0.1.0` |
| `0.0.1` | `0.1.0` | Minor (exists) | ✅ Auto-resolve | `0.2.0` |
| `0.1.0` | `1.0.0` | Major | ✅ Auto-resolve | `1.0.0` |
| `0.1.0` | `1.0.0` | Major (exists) | ✅ Auto-resolve | `2.0.0` |
| `0.1.0` | `0.0.2` | Patch | ❌ Manual | Backward targeting |
| `1.0.0` | `0.2.0` | Minor | ❌ Manual | Backward targeting |

#### Manual Resolution Guidance

When manual intervention is required, the CI pipeline provides clear guidance:

```
🚨 SEMANTIC VERSION CONFLICT DETECTED
=====================================
Current latest version: 1.0.0
Target version: 0.2.0 (patch increment)
Context: MR-123

This conflict requires human intervention to determine the correct version.

Possible resolutions:
1. Use patch increment: 1.0.1
2. Use minor increment: 1.1.0
3. Use major increment: 2.0.0

To resolve:
1. Create the appropriate version tag manually
2. Re-run this pipeline

Example: git tag 1.0.1 && git push origin 1.0.1
```

### Stale Feature Branch Tags (Backward Targeting)

When a feature branch has a manual version tag that's older than the current main branch version, this creates a "backward targeting" conflict that would result in timeline mismatches.

**Example Scenario:**
- Feature branch A creates manual tag `0.9.1` (patch increment)
- Feature branch B (no manual tag) merges to main, gets auto-incremented to `0.10.0` (minor increment)
- Feature branch A attempts to merge with its `0.9.1` tag

**Problem:** This would create a timeline where `0.9.1` appears after `0.10.0`, breaking semantic versioning principles.

**Detection:** The CI pipeline detects backward targeting when:
```bash
manual_version < main_branch_baseline
```

**Resolution:** This requires manual intervention to determine the correct semantic version. The appropriate choice depends on the nature of your changes:

**For the example above (patch-level changes):**
- **Patch to current main**: `0.10.1` (recommended - preserves the patch nature of your changes)

**For other scenarios, consider:**
- **Minor increment**: `0.11.0` (if your changes actually warrant a new minor release)
- **Major increment**: `1.0.0` (if your changes are breaking)

**Guidance:** Consider the scope and compatibility of your changes relative to the current main branch version.

**CI Behavior:** When backward targeting is detected, the pipeline will:
1. Block the merge with a clear error message
2. Provide specific version suggestions based on the main branch baseline
3. Require manual tag update before allowing the merge

**Example Error Message:**
```
🚨 BACKWARD TARGETING DETECTED
=====================================
Feature branch manual version: 0.9.1
Main branch baseline version: 0.10.0

This would create a timeline mismatch where 0.9.1 appears after 0.10.0.

This requires manual resolution to determine the correct semantic version:
1. Update your feature branch version tag:
   git tag -d 0.9.1
   git tag <appropriate_version>
   git push origin --tags
2. Re-run this pipeline

Consider the semantic scope of your changes relative to the current main branch.
```

## Git Tags

The version management system uses git tags as the single source of truth:
```bash
# View all version tags
git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$'

# Example output:
# 1.1.0
# 1.0.1
# 1.0.0
# 0.1.0
```

**Note**: Version tags are created only on main branch merges (for releases). Feature branches get Docker images with test versions for testing but do not create version tags.

### Tips

#### **Git Hooks for Automatic Tag Pushing**
Automate tag pushing to avoid forgetting the `--tags` flag:
```bash
# One-time setup
make install-version-hooks
```

**How it works:**
- Pre-push hook automatically pushes version tags when you push code
- No need to remember `--tags` flag or separate tag push commands
- Works with any `git push` command

**When to use:** If you frequently forget to push tags or want a more seamless workflow.

#### **Handle Semantic Version Concurrency Conflicts**
When multiple branches target the same tag versions:
```bash
# Create a specific version tag directly to resolve the conflict
git tag "1.2.3"
git push origin "1.2.3"
```

**When to use:** When resolving version concurrency conflicts that cannot be auto-resolved by the CI/CD pipeline.


## Docker Images

Images are tagged differently based on the branch type:

### **Feature Branches (Merge Requests):**
- **Tags**: Commit SHA only
- **Examples**: 
  - `gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:82a3791bf4c8ba64942181b64043a8786aa4aa8b` (commit SHA)
- **Purpose**: For testing and development

### **Main Branch (Releases):**
- **Tags**: Both semantic version AND commit SHA
- **Examples**: 
  - `gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:1.0.1` (semantic version)
  - `gitlab.aws.omniva.com:5050/ise/ccppday0/domains/ai/ai-gateway:abc123` (commit SHA)
- **Purpose**: For production releases

## Best Practices

### When to Use Each Bump Type

**PATCH (auto-incremented by CI):**
- Bug fixes
- Small improvements
- Documentation updates
- Dependency updates

**MINOR (manual bump):**
- New features
- New API endpoints
- Enhanced functionality
- Backward-compatible changes

**MAJOR (manual bump):**
- Breaking API changes
- Database schema changes
- Configuration changes
- Incompatible updates

### Commit Messages

Use clear, descriptive commit messages:
```bash
# Good
git commit -m "Add user authentication feature"
git commit -m "Fix memory leak in data processing"
git commit -m "Bump minor version for new API endpoints"

# Avoid
git commit -m "fix"
git commit -m "update"
```

### Version Bump Timing

- **Bug fixes**: Let CI auto-increment PATCH
- **Features**: Bump MINOR before merging to main
- **Breaking changes**: Bump MAJOR and document migration steps



### Conflict Prevention

- **Coordinate version bumps**: Communicate with team before manual version bumps
- **Avoid concurrent bumps**: Don't run manual version commands during active pipeline runs
- **Use descriptive commit messages**: Include version information in commit messages
- **Monitor pipeline status**: Check pipeline status before manual version operations

## Troubleshooting

### Common Problems and Solutions

#### **Problem: Pipeline fails with "Semantic version conflict detected"**
**Cause:** Multiple branches targeting the same version number or semantic conflict
**Solution:**
```bash
# Follow the guidance in the pipeline error message
# Example: Create the suggested version tag
git tag 1.0.1 && git push origin 1.0.1
# Then re-run the pipeline
```

#### **Problem: Version not auto-incrementing as expected**
**Cause:** Manual version tag exists or CI pipeline issues
**Diagnosis:**
```bash
# Check current latest version
git tag --sort=-version:refname | head -n1

# Check if manual version exists
git tag --list | grep "1.0.1"
```
**Solution:**
- If manual tag exists: CI will use it instead of auto-incrementing
- If no manual tag: Check pipeline logs for errors

#### **Problem: "Permission denied" when pushing tags**
**Cause:** CI token lacks tag push permissions
**Solution:**
```bash
# Push tag manually with your credentials
git tag 1.0.1 && git push origin 1.0.1
# Then re-run the pipeline
```

#### **Problem: Version conflicts between concurrent merges**
**Auto-resolvable conflicts:**
```bash
# Patch conflicts: 0.1.1 → 0.1.2 ✅
# Minor conflicts: 0.1.0 → 0.2.0 ✅
# Major conflicts: 1.0.0 → 2.0.0 ✅
```

**Manual intervention required:**
```bash
# Cross-level conflicts: patch vs minor → ❌ (requires decision)
# Backward targeting: 0.2.0 → 0.1.1 → ❌ (requires decision)
```

#### **Problem: Manual version bump not taking effect**
**Cause:** Tag already exists or wrong branch
**Solution:**
```bash
# Force update existing tag
git tag -f 1.1.0 && git push -f origin 1.2.0
```

### Quick Reference

| **Problem** | **Quick Fix** |
|-------------|---------------|
| Version conflict | Follow pipeline error guidance |
| Permission denied | Push tag manually |
| Version not incrementing | Check for existing manual tags |
| Concurrent merge conflicts | Use suggested auto-resolution |
| Manual bump not working | Use `make bump-*` commands |
