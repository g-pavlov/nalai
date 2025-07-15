# DevOps Pipeline

## Overview

This guide covers the technical implementation and operational aspects of the CI/CD pipeline for DevOps engineers.

## Pipeline Architecture

### **Workflow Structure**
| **Workflow** | **Trigger** | **Purpose** | **Jobs** |
|--------------|-------------|-------------|----------|
| **PR Checks** | Pull requests to main | Pre-merge validation | lint-and-test, security-check |
| **Feature Branch** | Pushes to feature branches | Development validation | lint-and-test, build-test, security-check |
| **CI/CD Pipeline** | Main pushes, version tags, manual | Production deployment | version-management, lint-and-test, build-and-push, security-scan, create-release |

### **Job Dependencies**
```
version-management → lint-and-test → build-and-push → security-scan → create-release
```

## Version Management

### **Auto-Increment Logic**
| **Scenario** | **Version Source** | **Behavior** |
|--------------|-------------------|--------------|
| **Main push** | Main branch baseline | Auto-increment patch (1.2.3 → 1.2.4) |
| **Manual tag** | Git tag | Use specified version |
| **Feature branch tag** | Manual tag | Override auto-increment |

### **Conflict Resolution**
| **Conflict Type** | **Resolution** | **Manual Action** |
|-------------------|----------------|-------------------|
| **Same level** | Auto-resolve | None required |
| **Cross level** | Manual intervention | Create appropriate tag |
| **Backward targeting** | Pipeline fails | Use higher version |

### **Version Utilities**
```bash
# Key functions in scripts/version_utils_github.sh
get_or_create_version          # Detect current version
increment_patch_version         # Auto-increment logic
detect_backward_targeting       # Validate version timeline
```

## Docker Image Strategy

### **Image Tags**
| **Branch/Tag** | **Image Tag** | **Purpose** |
|----------------|---------------|-------------|
| **Main branch** | `v1.2.3`, `latest` | Production releases |
| **Feature branch** | `abc1234` (commit SHA) | Development testing |
| **Version tag** | `v1.2.3` | Manual releases |

### **Registry Configuration**
- **Registry**: GitHub Container Registry (ghcr.io)
- **Authentication**: GITHUB_TOKEN (automatic)
- **Permissions**: Read/write packages

## Security Implementation

### **Security Scanning**
| **Scan Type** | **Tool** | **Target** | **Output** |
|---------------|----------|------------|------------|
| **Code Scan** | Trivy | Source code | SARIF to GitHub Security |
| **Container Scan** | Trivy | Docker images | SARIF to GitHub Security |
| **Dependency Scan** | Trivy | Dependencies | SARIF to GitHub Security |

### **Security Gates**
- **Critical vulnerabilities**: Pipeline fails
- **High vulnerabilities**: Warning, continues
- **Medium/Low**: Warning only

## Environment Configuration

### **Required Secrets**
| **Secret** | **Source** | **Purpose** |
|------------|------------|-------------|
| **GITHUB_TOKEN** | GitHub Actions | Registry access, API calls |
| **Additional secrets** | Repository settings | Deployment credentials |

### **Environment Variables**
```bash
# Version management
VERSION_TYPE=patch|minor|major

# Docker configuration
DOCKER_REGISTRY=ghcr.io
IMAGE_NAME=owner/repo

# Security configuration
TRIVY_SEVERITY=CRITICAL,HIGH
```

## Monitoring & Alerting

### **Key Metrics**
| **Metric** | **Target** | **Monitoring** |
|------------|------------|----------------|
| **Success Rate** | >95% | GitHub Actions dashboard |
| **Build Time** | <5 minutes | Workflow run logs |
| **Resource Usage** | <2000 minutes/month | GitHub Actions usage |
| **Security Issues** | 0 critical | GitHub Security tab |

### **Failure Patterns**
| **Pattern** | **Common Cause** | **Resolution** |
|-------------|------------------|----------------|
| **Version conflicts** | Manual version < baseline | Use higher version |
| **Build timeouts** | Resource constraints | Optimize Dockerfile |
| **Registry failures** | Authentication issues | Check GITHUB_TOKEN |
| **Security failures** | Vulnerable dependencies | Update dependencies |

## Operational Procedures

### **Pipeline Maintenance**
| **Task** | **Frequency** | **Action** |
|----------|---------------|------------|
| **Dependency updates** | Monthly | Update GitHub Actions versions |
| **Security patches** | As needed | Update vulnerable dependencies |
| **Performance review** | Quarterly | Optimize build times |
| **Documentation updates** | On changes | Update workflow documentation |

### **Troubleshooting**
| **Issue** | **Investigation** | **Resolution** |
|-----------|------------------|----------------|
| **Version conflicts** | Check git tags and version logic | Manual version tag |
| **Build failures** | Review Docker build logs | Fix Dockerfile issues |
| **Security failures** | Review Trivy reports | Update dependencies |
| **Registry issues** | Check authentication | Verify GITHUB_TOKEN |

## Testing Strategy

### **Pipeline Testing**
| **Test Type** | **Method** | **Frequency** |
|---------------|------------|---------------|
| **Version logic** | Manual tag testing | Before releases |
| **Build process** | Local Docker builds | Before changes |
| **Security scanning** | Local Trivy runs | Before deployments |
| **End-to-end** | Full pipeline execution | On major changes |

### **Local Testing Commands**
```bash
# Test version management
source scripts/version_utils_github.sh
get_or_create_version

# Test Docker build
make build-prod

# Test security scanning
make ci-security

# Test workflow dispatch
gh workflow run ci-cd.yml -f version_type=patch
```

## Container Best Practices

### **Security-First Approach**
- ✅ **Non-root user**: Application runs as system user with minimal permissions
- ✅ **No shell access**: Application user cannot spawn interactive shells
- ✅ **Principle of least privilege**: Only necessary directories owned by application user
- ✅ **Minimal attack surface**: No unnecessary files, directories, or development tools

### **Standard File System Layout**
- ✅ **Configuration**: `/etc/api-assistant/` (follows Linux FHS)
- ✅ **Logs**: `/var/log/api-assistant/` (standard system log location)
- ✅ **Application**: Python site-packages (standard Python location)
- ✅ **Clear separation**: Build stage uses `/build`, runtime has no working directory

### **Performance Optimizations**
- ✅ **Multi-stage builds**: Clear separation between build and runtime
- ✅ **Layer caching**: Optimized layer ordering for better cache utilization
- ✅ **Minimal footprint**: Eliminated unnecessary directories and files
- ✅ **Efficient operations**: Direct installation to system locations

## Best Practices

### **Pipeline Design**
- ✅ **Idempotent operations**: Safe to re-run
- ✅ **Clear error messages**: Actionable failure information
- ✅ **Resource optimization**: Minimize build times
- ✅ **Security first**: Scan early, fail fast

### **Operational Excellence**
- ✅ **Monitor metrics**: Track success rates and performance
- ✅ **Document changes**: Update procedures when pipeline changes
- ✅ **Test thoroughly**: Validate changes before production
- ✅ **Plan rollbacks**: Have recovery procedures ready 