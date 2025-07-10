# Ollama Development Strategy - Efficient Model Path Usage

This document describes the efficient model path strategy implemented for development scenarios to avoid unnecessary model downloads and improve development workflow.

## Overview

The development setup script (`scripts/setup_ollama_dev.sh`) implements a three-tier strategy for using Ollama models efficiently:

1. **Environment Variable Priority**: If `OLLAMA_MODELS_PATH` is set, use that path
2. **Well-Known Path Detection**: Check common Ollama installation paths on the host system
3. **Containerized Fallback**: Use fully containerized models if no existing models are found

## Strategy Details

### 1. Environment Variable Priority

If the `OLLAMA_MODELS_PATH` environment variable is set, the script will:
- Validate that the path contains valid Ollama models
- Mount this path directly into the container
- Use existing models without downloading

```bash
export OLLAMA_MODELS_PATH="/path/to/your/ollama/models"
make serve-dev
```

### 2. Well-Known Path Detection

The script automatically checks these common Ollama installation paths:
- `$HOME/.ollama` (default Ollama installation)
- `/usr/local/share/ollama`
- `/opt/ollama`
- `/var/lib/ollama`

If any of these paths contain valid Ollama models, they will be mounted and used.

### 3. Containerized Fallback

If no existing models are found, the script will:
- Use Docker volumes for model storage
- Download models as needed
- Provide a fully containerized experience

## Usage

### Basic Usage

```bash
# Start development environment with efficient model path strategy
make serve-dev

# Stop development services
make stop-dev
```

### Custom Model Configuration

You can customize the model and other settings using environment variables:

```bash
# Use a specific model
export OLLAMA_MODEL="llama3.1:8b"
make serve-dev

# Use a custom port
export OLLAMA_PORT="11435"
make serve-dev

# Specify a custom models path
export OLLAMA_MODELS_PATH="/custom/path/to/models"
make serve-dev
```

### Available Environment Variables

- `OLLAMA_MODEL`: Model to use (default: `llama3.1:8b`)
- `OLLAMA_PORT`: Port for Ollama service (default: `11434`)
- `OLLAMA_MODELS_PATH`: Custom path to existing Ollama models
- `OLLAMA_TARGET_OS`: Target OS for model compatibility (auto-detected)
- `OLLAMA_TARGET_ARCH`: Target architecture for model compatibility (auto-detected)

## Generated Configuration

The script generates a `docker-compose.dev.yml` file that includes:

- **API Assistant**: Development server with hot reload
- **Ollama**: LLM service with efficient model mounting
- **Ecommerce Mock**: Mock API service for testing

### Volume Mounting Strategy

When existing models are found:
```yaml
volumes:
  - /path/to/existing/models:/root/.ollama  # Mount existing models
  - ./models:/models                        # Additional model storage
  - ./ollama_config:/etc/ollama            # Configuration
```

When no existing models are found:
```yaml
volumes:
  - ollama_data:/root/.ollama              # Docker volume for models
  - ./models:/models                        # Additional model storage
  - ./ollama_config:/etc/ollama            # Configuration
```

## Benefits

1. **Faster Startup**: No need to download models if they already exist
2. **Disk Space Efficiency**: Reuse existing model installations
3. **Development Flexibility**: Easy switching between different model configurations
4. **Consistent Environment**: Same setup across different development machines
5. **Fallback Safety**: Always works, even without existing models

## Troubleshooting

### Model Not Found

If the script doesn't detect your existing models:

1. Check if the path contains valid Ollama model files:
   ```bash
   ls -la /path/to/your/ollama/models/
   ```

2. Set the path explicitly:
   ```bash
   export OLLAMA_MODELS_PATH="/path/to/your/ollama/models"
   make serve-dev
   ```

### Permission Issues

If you encounter permission issues with mounted volumes:

1. Check file permissions:
   ```bash
   ls -la /path/to/your/ollama/models/
   ```

2. Ensure the Docker user can access the mounted directory

### Model Download Issues

If model downloads fail:

1. Check internet connectivity
2. Verify the model name is correct
3. Check Docker logs:
   ```bash
   docker compose -f docker-compose.dev.yml logs ollama
   ```

## Integration with Existing Workflow

This strategy integrates seamlessly with the existing development workflow:

- **Local Development**: Use `make serve` for local development without Ollama
- **Ollama Development**: Use `make serve-dev` for development with Ollama
- **Production**: Use `make serve-prod` for production deployment

The script automatically handles the complexity of model path detection and configuration, allowing developers to focus on their application logic. 