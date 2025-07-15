# Developer Workflow

## Overview

This guide explains how the CI/CD pipeline affects your development workflow and what you need to know to work effectively.

## Branch Strategy

| **Branch** | **CI Behavior** | **Deployment** | **Use Case** |
|------------|-----------------|----------------|--------------|
| **main** | Full pipeline | ✅ Production | Protected, production-ready code |
| **feature/** | Tests only | ❌ None | Development and testing |
| **v* tags** | Full pipeline | ✅ Production | Manual releases and hotfixes |

## What Happens Automatically

### **On Every Push**
- ✅ **Code Quality**: Linting and formatting checks
- ✅ **Unit Tests**: pytest execution with coverage
- ✅ **Security Scan**: Vulnerability detection with Trivy

### **On Main Branch Push**
- ✅ **Version Management**: Auto-increment from main baseline
- ✅ **Docker Build**: Production image with semantic version
- ✅ **Security Scan**: Container vulnerability scanning
- ✅ **Release Creation**: GitHub release with changelog

### **On Version Tags**
- ✅ **Manual Version**: Uses your specified version
- ✅ **Full Pipeline**: Same as main branch push

## What Requires Manual Action

| **Scenario** | **Action Required** | **When** |
|--------------|-------------------|----------|
| **Breaking Changes** | Manual major version bump | Before merging to main |
| **Security Vulnerabilities** | Update dependencies | When Trivy reports issues |
| **Pipeline Failures** | Fix and re-push | When CI checks fail |
| **Hotfixes** | Create version tag | For urgent production fixes |

## Development Workflow

### **Feature Development**
```bash
# 1. Create feature branch
git checkout -b feature/new-feature

# 2. Make changes and test locally
make lint
make test

# 3. Push to trigger CI
git push origin feature/new-feature

# 4. Create PR to main
# CI runs: lint, test, security scan
```

### **Breaking Changes**
```bash
# 1. Bump major version on feature branch
make bump-major

# 2. Push code and tags
git add --all && git push origin feature/breaking-change --tags

# 3. Merge to main
# CI uses your manual version
```

### **Hotfixes**
```bash
# 1. Create version tag
git tag v1.2.4
git push origin v1.2.4

# 2. CI automatically builds and deploys
```

## Quality Gates

### **Pre-Deployment Checks**
| **Gate** | **What It Checks** | **Failure Action** |
|----------|-------------------|-------------------|
| **Version Management** | Semantic versioning, no conflicts | ❌ Pipeline stops |
| **Code Quality** | Ruff linting and formatting | ❌ Pipeline stops |
| **Unit Tests** | pytest execution | ❌ Pipeline stops |
| **Security** | Vulnerability scanning | ⚠️ Warning, continues |

### **Post-Deployment Checks**
| **Gate** | **What It Checks** | **Failure Action** |
|----------|-------------------|-------------------|
| **Docker Build** | Image creation and verification | ❌ Pipeline stops |
| **Container Security** | Image vulnerability scan | ⚠️ Warning, continues |
| **Release Creation** | GitHub release generation | ❌ Pipeline stops |

## Common Issues & Solutions

### **Pipeline Failures**
| **Issue** | **Quick Fix** | **Command** |
|-----------|---------------|-------------|
| **Linting Errors** | Fix code style | `make lint` |
| **Test Failures** | Fix failing tests | `make test` |
| **Version Conflicts** | Use higher version | `make bump-minor` |
| **Build Failures** | Check Dockerfile | `make build-prod` |

### **Local Testing**
```bash
# Test same checks as CI
make lint          # Code quality
make test          # Unit tests
make build-prod    # Docker build
make ci-security   # Security scan
```

## Monitoring

### **Pipeline Health**
- **Success Rate**: >95% (monitor in GitHub Actions)
- **Build Time**: <5 minutes
- **Security Issues**: 0 critical vulnerabilities

### **Key URLs**
- **Actions**: `https://github.com/repo/actions`
- **Releases**: `https://github.com/repo/releases`
- **Security**: `https://github.com/repo/security`

## Best Practices

### **Before Pushing**
- ✅ Run `make lint` and `make test` locally
- ✅ Use semantic commit messages
- ✅ Check for security vulnerabilities

### **Version Management**
- ✅ Let CI auto-increment for normal changes
- ✅ Manual version bumps for breaking changes
- ✅ Use semantic versioning (MAJOR.MINOR.PATCH)

### **Pipeline Monitoring**
- ✅ Check GitHub Actions dashboard regularly
- ✅ Address security issues promptly
- ✅ Monitor build times and success rates 