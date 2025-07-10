# Ollama Setup with Docker Compose

This guide explains how to set up Ollama with llama3.1:8b using Docker Compose with parameterized configuration for different architectures and operating systems.

## Overview

The setup includes:
- **Parameterized Docker Compose configuration** for different architectures (AMD64, ARM64)
- **Automatic system detection** for optimal configuration
- **GPU support** for NVIDIA GPUs and Apple Silicon
- **CPU-only fallback** for systems without GPU acceleration
- **Easy-to-use setup scripts** for quick deployment

## Quick Start

### 1. Basic Setup (Recommended)

Run the advanced setup script that automatically detects your system:

```bash
./scripts/setup_ollama_advanced.sh
```

This script will:
- Detect your system architecture and OS
- Configure GPU support if available
- Start Ollama with the optimal configuration
- Download the llama3.1:8b model

### 2. Manual Setup

If you prefer manual configuration:

```bash
# Set environment variables
export OLLAMA_PORT=11434
export OLLAMA_MODEL=llama3.1:8b
export OLLAMA_TARGET_OS=linux
export OLLAMA_TARGET_ARCH=amd64

# Start Ollama service
docker compose -f docker-compose.dev.yml up -d
```

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_PORT` | `11434` | Port for Ollama API |
| `OLLAMA_MODEL` | `llama3.1:8b` | Model to download and use |
| `OLLAMA_TARGET_OS` | `linux` | Target operating system |
| `OLLAMA_TARGET_ARCH` | `amd64` | Target architecture |

### Architecture Support

The setup supports multiple architectures:

#### AMD64 (x86_64)
```bash
# For Intel/AMD 64-bit systems
export OLLAMA_TARGET_ARCH=amd64
docker compose -f docker-compose.dev.yml up -d
```

#### ARM64 (Apple Silicon, ARM servers)
```bash
# For Apple Silicon Macs and ARM64 servers
export OLLAMA_TARGET_ARCH=arm64
docker compose -f docker-compose.dev.yml up -d
```

#### CPU-Only Mode
```bash
# For systems without GPU acceleration
docker compose -f docker-compose.dev.yml up -d
```

## GPU Support

### NVIDIA GPU
The setup automatically detects NVIDIA GPUs and enables GPU acceleration:

```bash
# Check if NVIDIA GPU is detected
nvidia-smi

# Start with GPU support
./scripts/setup_ollama_advanced.sh
```

### Apple Silicon
For Apple Silicon Macs, the setup uses optimized configurations:

```bash
# Automatically detected on Apple Silicon
./scripts/setup_ollama_advanced.sh
```

## Available Models

You can use different models by changing the `OLLAMA_MODEL` variable:

```bash
# Use different models
export OLLAMA_MODEL=llama3.1:8b
export OLLAMA_MODEL=llama3.1:70b
export OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M
export OLLAMA_MODEL=codellama:7b
export OLLAMA_MODEL=phi:latest

# Run setup with custom model
./scripts/setup_ollama_advanced.sh -m llama3.1:8b
```

## Integration with API Assistant

The Ollama service is integrated with your API Assistant:

```yaml
# In docker-compose.yml
services:
  api-assistant:
    # ... existing configuration ...
    depends_on:
      - ollama
```

### Configuration for API Assistant

To use Ollama with your API Assistant, update your model configuration:

```python
# Example configuration in your API Assistant
OLLAMA_BASE_URL = "http://ollama:11434"
OLLAMA_MODEL = "llama3.1:8b"
```

## Management Commands

### Start Services
```bash
# Start with auto-detection
./scripts/setup_ollama_advanced.sh

# Start specific profile
docker compose -f docker-compose.dev.yml up -d
```

### Stop Services
```bash
# Stop all Ollama services
docker compose -f docker-compose.dev.yml down

# Stop specific service
docker compose -f docker-compose.dev.yml stop ollama
```

### View Logs
```bash
# View Ollama logs
docker compose -f docker-compose.dev.yml logs ollama

# Follow logs in real-time
docker compose -f docker-compose.dev.yml logs -f ollama
```

### Check Status
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# List available models
curl http://localhost:11434/api/tags | jq '.models[] | .name'
```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Change port
export OLLAMA_PORT=11435
./scripts/setup_ollama_advanced.sh -p 11435
```

#### 2. GPU Not Detected
```bash
# Check NVIDIA drivers
nvidia-smi

# Use CPU-only mode
docker compose -f docker-compose.dev.yml up -d
```

#### 3. Model Download Fails
```bash
# Check internet connection
curl -I https://ollama.ai

# Retry download
curl -X POST http://localhost:11434/api/pull \
  -H "Content-Type: application/json" \
  -d '{"name": "llama3.1:8b"}'
```

#### 4. Insufficient Memory
```bash
# Use smaller model
export OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M
./scripts/setup_ollama_advanced.sh -m llama3.1:8b-instruct-q4_K_M
```

### Performance Optimization

#### Memory Usage
- **llama3.1:8b**: ~8GB RAM
- **llama3.1:8b-instruct-q4_K_M**: ~4GB RAM
- **llama3.1:70b**: ~40GB RAM

#### GPU Memory
- **NVIDIA GPU**: Minimum 8GB VRAM for 8B models
- **Apple Silicon**: Uses unified memory

## Advanced Configuration

### Custom Model Configuration

Create a custom model configuration:

```bash
# Create custom model file
cat > ollama_config/custom-model.modelfile << EOF
FROM llama3.1:8b

# Set system prompt
SYSTEM """You are a helpful AI assistant."""

# Set parameters
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
EOF

# Create custom model
curl -X POST http://localhost:11434/api/create \
  -H "Content-Type: application/json" \
  -d '{"name": "custom-assistant", "modelfile": "ollama_config/custom-model.modelfile"}'
```

### Environment-Specific Configuration

Create environment-specific configurations:

```bash
# Development
export OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M
export OLLAMA_PORT=11434

# Production
export OLLAMA_MODEL=llama3.1:8b
export OLLAMA_PORT=11435
```

## Security Considerations

### Network Security
- Ollama is configured to accept connections from any origin (`OLLAMA_ORIGINS=*`)
- Consider restricting access in production environments
- Use reverse proxy with authentication for public deployments

### Resource Limits
```yaml
# Add resource limits to docker-compose.dev.yml
services:
  ollama:
    # ... existing configuration ...
    deploy:
      resources:
        limits:
          memory: 16G
          cpus: '4.0'
        reservations:
          memory: 8G
          cpus: '2.0'
```

## Monitoring and Logging

### Health Checks
The setup includes health checks to ensure Ollama is running properly:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

### Logging
```bash
# View structured logs
docker compose -f docker-compose.dev.yml logs --tail=100 ollama

# Export logs
docker compose -f docker-compose.dev.yml logs ollama > ollama.log
```

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review Ollama documentation: https://ollama.ai/docs
3. Check Docker and Docker Compose logs
4. Verify system requirements and prerequisites 