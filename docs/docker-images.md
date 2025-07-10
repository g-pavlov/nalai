# Docker Images

## Quick Start

```bash
make build      # Development image
make build-prod # Production image
make serve      # Run with hot reload
make serve-prod # Run production container
```

## Performance Metrics

```bash
# Docker build analysis tools removed
```

### Build Times
| Scenario | Development [outdated] | Production | Cache Status |
|----------|-------------|------------|--------------|
| **No changes (Hot Cache)** | ~1s | ~7s | All layers cached |
| **Code changes (Partial Cache)** | ~55s | ~3s | Dependencies cached, app code rebuilt |
| **Dependency changes (Cold start, No Cache)** | ~1m 50s | ~49s | Full rebuild when pyproject.toml or dependencies change |

### Push Times (CI/CD)

**Push strategy**: Single tag push to avoid duplicate image uploads

| Configuration | Time | 
|---------------|------|
| **Production** | ~10s |
| **Development** | ~10s |


### Image Sizes
| Image | Size | Optimization |
|-------|------|--------------|
| **Production** | 871.73MB | Multi-stage build with uv |
| **Development** | 1.65GB | Editable packages |

### Layer Cache Efficiency

| Layer | Size | Cache Rate | Description |
|-------|------|------------|-------------|
| **Base System** | 97.2MB | 100% | Debian slim base image |
| **Python Setup** | 43.6MB | 100% | Python 3.12.11 installation |
| **System Dependencies** | 4.68MB | 100% | curl, ca-certificates |
| **Kubectl Installation** | 56.4MB | 100% | Kubernetes CLI tool |
| **Python Dependencies** | 713MB | 95% | uv-installed packages |
| **App Code** | 15.3KB | 0% | Source code, changes frequently |
| **Config Files** | 2.5KB | 90% | logging.yaml, certificates |
| **User Setup** | 26.8KB | 100% | ai-gateway user creation |
| **Total** | **925MB** | **87.5%** | **8/8 layers optimized** |

**Cache Strategy**:
- Base layers (System + Python): Always cached
- Dependencies: 95% cached when pyproject.toml unchanged
- Application code: 0% cached (changes frequently)

## Key Optimizations

### 1. Multi-stage Build (Production)
- **Build stage**: Generates requirements.txt using Poetry with public registry
- **Runtime stage**: Installs dependencies from requirements.txt using uv for speed
- **Layer separation**: Build tools removed after dependency installation

### 2. Fast Dependency Installation
- **uv package manager**: Ultra-fast parallel dependency installation
- **System installation**: `--system` flag for containerized environments
- **Index strategy**: `--index-strategy unsafe-best-match` for compatibility

### 3. Production Cleanup
- **Build tools removal** - gcc, build-essential purged
- **Cache cleanup** - apt, pip, poetry caches removed
- **Python optimization** - .pyc files, __pycache__ removed
- **uv removal** - Package manager removed after installation

### 4. CI/CD Push Optimization
- **Single tag push** - Avoids `--all-tags` duplicate uploads
- **Layer reuse** - Registry deduplication for faster pushes
- **Network efficiency** - 93% reduction in push time

## Architecture

### Optimization Goals
The build system balances **build time** vs **image size** optimization. 
The multi-stage build approach reduces image size while maintaining build efficiency.

### Production Container (`Dockerfile`)
```
Stage 1 (Build):
  - System setup (cached)
  - Python + Poetry (cached)
  - Registry configuration
  - Requirements.txt generation
  - Package data preparation

Stage 2 (Runtime):
  - System setup (cached)
  - Python + uv (cached)
  - Dependencies from requirements.txt (cached unless pyproject.toml changes)
  - App code (invalidated by code changes)
  - uv removal for size optimization
```

### Development Container (`Dockerfile.dev`)
```
Layer 1: System setup (cached)
Layer 2: Python + tools (cached)
Layer 3: Dependencies (cached unless pyproject.toml changes)
Layer 4: Packages (editable installation)
Layer 5: App code (invalidated by code changes)
```

## Build Commands

### Development
```bash
make setup      # Create .env with required variables
make serve      # Run with hot reload (port 8080)
make build      # Build development image
```

### Production
```bash
make build-prod # Build optimized production image
make serve-prod # Run production container
```

## Environment Setup

Required `.env` variables:
```bash
AUTH0_CLIENT_ID=your_auth0_client_id
AUTH0_CLIENT_SECRET=your_auth0_client_secret
AUTH0_CLIENT_ID=your_auth0_client_id
AUTH0_CLIENT_SECRET=your_auth0_client_secret
AWS_SHARED_CREDENTIALS_FILE=/home/ai-gateway/.aws/credentials
AWS_CONFIG_FILE=/home/ai-gateway/.aws/config
```

### Fail-Fast Environment Checks
The Makefile includes pre-checks for required environment variables:
- `AUTH0_CLIENT_ID` and `AUTH0_CLIENT_SECRET` validation before Docker builds
- AWS credentials path configuration
- Environment variable validation with helpful error messages

## Package Data Management

### API Specifications
- **Location**: `packages/api-assistant/api_assistant/api_specs/`
- **Access**: Via `importlib.resources` for runtime access
- **Docker**: Automatically included as package data
- **No manual copying**: Handled by Poetry package installation

## Python requirements.txt Generation

### Two-Stage Requirements Process
1. **Poetry Export**: Generates requirements.txt with local packages as editable installs
2. **Non-Editable Conversion**: Converts editable installs to regular installs for production

### Scripts
- `scripts/generate_clean_requirements.py`: Excludes local packages (for analysis)
- `scripts/generate_prod_requirements.py`: Includes local packages as non-editable installs

### Registry Integration
- **Authentication**: Standard PyPI package management
- **URL Format**: `https://pypi.org/simple/`
- **Scope**: Public package access

## Recent Updates (v0.1.16)

### Multi-stage Build Implementation
- **Build Stage**: Generates requirements.txt using Poetry with public registry
- **Runtime Stage**: Installs dependencies using uv package manager for ultra-fast parallel installation
- **Optimization**: Build tools and requirements.txt removed after installation

### User and Security Improvements
- **User**: Changed from `app` to `ai-gateway` user with home directory `/home/ai-gateway`
- **Security**: Non-root user execution maintained with improved naming
- **Cleanup**: requirements.txt removed after dependency installation to reduce image size

### Package Data Management
- **API Specifications**: Moved to `packages/api-assistant/api_assistant/api_specs/`
- **Runtime Access**: Via `importlib.resources` for proper package data access
- **Docker Integration**: Automatically included as package data, no manual copying required

### Environment and Authentication
- **Fail-fast Validation**: Makefile checks for required environment variables before builds
- **Public Registry**: Standardized PyPI package management across development and production
- **AWS Credentials**: Added path configuration for containerized environments

### Build Optimization
- **uv Package Manager**: Ultra-fast parallel dependency installation with `--system` flag
- **Warning Suppression**: Environment variable configuration to suppress pip warnings
- **Layer Optimization**: Improved caching and cleanup for smaller final images

## Production Validation

The production image undergoes comprehensive validation to ensure security, functionality, and optimization. The validation covers:

### Security & Compliance
- **Non-root execution**: Container runs as `ai-gateway` user (uid=1000)
- **Build tools removal**: Multi-stage build ensures no build tools (gcc, make) in runtime image
- **Dev dependency exclusion**: No development tools (pytest, ruff, etc.) in production image

### Functionality & Health
- **Application startup**: Container starts and becomes ready within 30 seconds
- **Health endpoint**: `/health` endpoint responds with `{"status": "Healthy"}`
- **Environment configuration**: All required environment variables properly loaded

### Build Quality
- **Dependency classification**: All dependencies properly categorized as dev vs production
- **Image optimization**: Multi-stage build produces minimal runtime image
- **Package data access**: API specifications accessible via importlib.resources

**Validation Commands**: See `scripts/test-production-build-e2e.sh` for the complete validation suite.

## Future Optimizations

### Multi-stage Builds
**Status**: ✅ **Implemented** - Separate build and runtime environments   
**Benefit**: Smaller final image (~925MB vs previous 1.11GB)   
**Implementation**: Build stage generates requirements.txt, runtime stage installs with uv   
**Performance**: Maintains build speed while reducing image size   

### Alpine Base Image
**Potential**: Smaller base image (~180MB vs 276MB)   
**Benefit**: 35% reduction in base image size   
**Caveat**: 
- Compatibility issues with native Python packages (pyarrow, numpy)
- musl libc differences cause runtime errors
- Debugging is harder due to minimal tools
**Status**: Streamlit and pyarrow have known Alpine compatibility issues

### Wheel Building
**Potential**: Pre-built packages for faster installation
**Benefit**: 20-30s faster dependency installation   
**Caveat**:
- **Inter-package dependencies**: Local packages with `dev-dependencies` create circular build requirements
- **Complexity**: Multi-stage builds require careful dependency ordering and parallelization
- **Cache invalidation**: Wheel cache layers become complex with frequent code changes
- **Build time**: Sequential wheel building adds 5+ minutes; parallel reduces to ~1m 30s but increases complexity
**Status**: Current uv-based installation provides optimal build time vs complexity balance. Wheel building viable only with significant refactoring of package dependencies and build process.

### Distroless Images
**Potential**: Minimal runtime image (~120MB)   
**Benefit**: 90% smaller image, improved security   
**Caveat**:   
- No shell access for debugging
- Limited runtime introspection
- Complex debugging workflow
- Harder to troubleshoot production issues
**Status**: Development and debugging requirements outweigh size benefits 