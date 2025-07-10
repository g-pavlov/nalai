# Experimental Scripts

This folder contains experimental build optimization tools that are not part of the core build or runtime functionality.

## Scripts

### `build_wheels.py`
- **Purpose**: Optimized wheel building for all packages
- **Functionality**: Builds wheels for all packages and exports requirements.txt
- **Usage**: `poetry run python scripts/experimental/build_wheels.py`

### `production_build.sh`
- **Purpose**: Complete production build process with wheels and cleanup
- **Functionality**: Generates configs, builds wheels, installs dependencies, exports requirements, cleans artifacts
- **Usage**: `make build-prod-wheels` (runs inside Docker container)

## Usage

These scripts are **experimental** and not part of the core test suite. They are useful for:

- Optimizing Docker builds with pre-built wheels
- Reducing build time through parallel wheel building
- Understanding build performance and optimization

## Dependencies

- Docker must be running
- `.env` file with Auth0 configuration required
- Poetry environment with required dependencies

## Notes

- These scripts are **not tested** in the main test suite
- They are **experimental** and may change without notice
- Use at your own risk for development and debugging purposes 