# CI Pipeline Testing

## Quick Start

```bash
make test-pipeline
```

## What It Tests

| CI Stage | Job | Tests |
|----------|-----|-------|
| **build** | Increment Version | Main branch only, env vars, artifacts |
| **build** | Build | MR vs main logic, version handling |
| **deploy** | Deploy to Staging | Main branch only, deployment vars |

## Workflow Scenarios

### Merge Request Path
```
Increment Version: ❌ SKIPPED
Build: ✅ RUNS (commit SHA)
Deploy: ❌ SKIPPED
```

### Main Branch Path
```
Increment Version: ✅ RUNS (semantic version)
Build: ✅ RUNS (semantic version)
Deploy: ✅ RUNS (staging)
```

## Key Validations

- **Environment Variables** - Required CI vars present and validated
- **Artifacts** - `build.env` creation/consumption
- **Branch Logic** - MR vs main branch behavior
- **Script Integration** - CI variable usage in scripts
- **Error Handling** - Missing vars cause proper failures

## Usage Examples

```bash
# Full pipeline test
make test-pipeline

# Specific scenarios
bats .ci/test/test-pipeline-bats.bats -f "merge request"
bats .ci/test/test-pipeline-bats.bats -f "main branch"

# Debug specific jobs
bats .ci/test/test-pipeline-bats.bats -f "Increment Version job"
bats .ci/test/test-pipeline-bats.bats -f "Build job"
```

## Setup

```bash
make setup-bats
```

## Benefits

- **Workflow-Centric** - Tests actual CI behavior, not syntax
- **Direct Mapping** - Tests match CI configuration rules exactly
- **Integration Focus** - Validates script interactions and data flow
- **Branch Logic** - Ensures proper MR vs main branch handling

## Files

- **Tests:** `.ci/test/test-pipeline-bats.bats`
- **CI Config:** CI configuration files
- **Scripts:** `.ci/increment_version.sh`, `.ci/create_and_push_image.sh`, `.ci/update_deployment_config.sh` 