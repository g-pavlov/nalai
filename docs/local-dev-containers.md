# Local Development Container Environment

This document describes how to set up and use the local development container environment for the API Assistant project.

## Overview

The project uses Docker Compose to provide a complete local development environment with all necessary services containerized, including the API Assistant application and Ollama for local LLM inference.

## Prerequisites

- Docker and Docker Compose installed
- Git for version control
- Make (optional, for convenience commands)

## Quick Start

1. **Clone and setup:**
   ```bash
   git clone <repository>
   cd integration_assistant
   make setup-dev
   ```

2. **Start the development environment:**
   ```bash
   docker-compose up -d
   ```

3. **Access services:**
   - API Assistant: http://localhost:8080
   - Ollama API: http://localhost:11434
   - Ecommerce Mock API: http://localhost:8000

## Container Architecture

### Services

- **nalai**: Main application server
  - Port: 8080
  - Environment: Development with hot reload
  - Volumes: Source code mounted for live updates
  - Health check: `/healthz` endpoint
  - Dependencies: Requires ollama and ecommerce-mock services

- **ollama**: Local LLM inference service
  - **Service**: `ollama/ollama:latest` container
  - **Storage**: Docker volume `ollama_data:/root/.ollama`
  - **Host Mount**: `./models:/models` for faster startup
  - **Resources**: 12GB memory, 10 CPUs max

- **ecommerce-mock**: Demo API service
  - Port: 8000
  - Purpose: Provides mock ecommerce API for testing
  - Health check: `/health` endpoint

### Data Persistence

- **ollama_data**: Ollama models and configuration (persistent volume)
- **./logs**: Application logs (host mounted)
- **./data**: Application data (host mounted)
- **./models**: Host models directory (optional, for faster startup)

### Container Configuration

The containers are configured with production-like settings for a realistic development environment:

- **Health checks** on all services for monitoring
- **Resource limits** to prevent system overload
- **Restart policies** for reliability
- **Volume mounts** for data persistence and development convenience
- **Environment configuration** via `.env` files

## Development Workflow

### Starting Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f nalai

# Stop services
docker-compose down
```

### Code Changes

The application container mounts the source code, so changes are reflected immediately:

```bash
# Make code changes in your editor
# The application will automatically reload
```

### Model Management

```bash
# Pull a model to Ollama
docker-compose exec ollama ollama pull llama2:7b

# List available models
docker-compose exec ollama ollama list

# Remove a model
docker-compose exec ollama ollama rm llama2:7b
```

### Testing

```bash
# Run tests in container
docker-compose exec nalai make test

# Run specific test suites
docker-compose exec nalai make test-unit
docker-compose exec nalai make test-integration
```

## Development Environment Containers Overview

### Ollama Model Server

- **Local LLM testing** without external API costs
- **Offline development** capabilities
- **Model experimentation** with different LLMs locally

#### **Implementation**
| **Component** | **Details** |
|---------------|-------------|
| **Service** | `ollama/ollama:latest` container |
| **Storage** | Docker volume `ollama_data:/root/.ollama` |
| **Host Mount** | `./models:/models` for faster startup |
| **Resources** | 12GB memory, 10 CPUs max |

#### **Model Loading Strategy**
| **Priority** | **Source** | **Purpose** |
|--------------|------------|-------------|
| **1st** | Environment variable `OLLAMA_MODELS_PATH` | Custom model path |
| **2nd** | Host mount `./models:/models` | Pre-downloaded models |
| **3rd** | Docker volume `ollama_data:/root/.ollama` | Persistent storage |
| **4th** | Auto-download | On-demand model fetching |

#### **Configuration Options**
| **Variable** | **Default** | **Purpose** |
|--------------|-------------|-------------|
| `OLLAMA_PORT` | `11434` | Ollama API port |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | API Assistant connection |

#### **Operations**

```bash
# Start only Ollama
docker-compose up -d ollama

# Stop only Ollama
docker-compose stop ollama

# View logs
docker-compose logs ollama

# Check if running
curl http://localhost:11434/api/tags
```

### **Access**
| **Service** | **URL** | **Purpose** |
|-------------|---------|-------------|
| **Ollama API** | `http://localhost:11434` | Direct Ollama access |
| **API Assistant** | `http://localhost:8080` | Your app with Ollama integration |
| **Mock API** | `http://localhost:8000` | Test API endpoints |
| **OpenAI API** | `http://localhost:8080/v1` | OpenAI-compatible endpoint |

**Note**: Models are downloaded automatically on first use and stored persistently.

### ECommerce API Server

- **Mock API testing** for integration development
- **Realistic API responses** for development scenarios
- **No external dependencies** for offline development

#### **Implementation**
| **Component** | **Details** |
|---------------|-------------|
| **Service** | Custom mock service container |
| **Storage** | In-memory data store |
| **Port** | 8000 |
| **Health Check** | `/health` endpoint |

#### **Configuration Options**
| **Variable** | **Default** | **Purpose** |
|--------------|-------------|-------------|
| `MOCK_API_PORT` | `8000` | Mock API port |
| `MOCK_API_BASE_URL` | `http://localhost:8000` | API Assistant connection |

#### **Operations**
```bash
# Start only mock API
docker-compose up -d ecommerce-mock

# Stop only mock API
docker-compose stop ecommerce-mock

# View logs
docker-compose logs ecommerce-mock

# Check if running
curl http://localhost:8000/health
```

### API Assistant Service

- **Main application server** with hot reload

#### **Implementation**
| **Component** | **Details** |
|---------------|-------------|
| **Service** | Custom API Assistant container |
| **Storage** | Host-mounted source code, data and logs |
| **Port** | 8080 |
| **Health Check** | `/healthz` endpoint |
| **Dependencies** | Requires ollama and ecommerce-mock |

#### **Configuration Options**
All applicable from project configuration.

#### **Operations**
```bash
# Start only API Assistant
docker-compose up -d nalai

# Stop only API Assistant
docker-compose stop nalai

# View logs
docker-compose logs nalai

# Check if running
curl http://localhost:8080/healthz
```

## Configuration

### Environment Variables

Key environment variables for local development:

```yaml
# docker-compose.yml
environment:
  - OLLAMA_BASE_URL=http://ollama:11434
  - LOG_LEVEL=DEBUG
  - ENVIRONMENT=development
```

### Model Configuration

Configure which models to use in `src/nalai/config.py`:

```python
OLLAMA_MODELS = {
    "llama2:7b": "http://ollama:11434",
    "llama2:13b": "http://ollama:11434",
    "codellama:7b": "http://ollama:11434"
}
```

## Troubleshooting

### Common Issues

1. **Port conflicts:**
   ```bash
   # Check what's using the ports
   lsof -i :8000
   lsof -i :11434
   lsof -i :3000
   ```

2. **Container won't start:**
   ```bash
   # Check container logs
   docker-compose logs nalai
   docker-compose logs ollama
   ```

3. **Model loading issues:**
   ```bash
   # Check Ollama status
   docker-compose exec ollama ollama list
   
   # Restart Ollama service
   docker-compose restart ollama
   ```

### Performance Optimization

- **GPU Acceleration**: Add GPU support to Ollama container:
  ```yaml
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  ```

- **Memory Limits**: Adjust container memory limits based on your system:
  ```yaml
  deploy:
    resources:
      limits:
        memory: 4G
  ```

## Development Commands

### Make Commands

```bash
# Setup development environment
make setup-dev

# Start containers
make dev-up

# Stop containers
make dev-down

# View logs
make dev-logs

# Run tests
make test

# Lint code
make lint
```

### Docker Compose Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Rebuild containers
docker-compose build

# View logs
docker-compose logs -f

# Execute commands in containers
docker-compose exec nalai bash
docker-compose exec ollama ollama list
```

## Production vs Development

This container setup is designed for local development only. For production:

- Use production Docker images
- Implement proper service discovery
- Configure external LLM services
- Set up monitoring and logging
- Use production-grade orchestration (Kubernetes, etc.)

## Next Steps

- [Development Guide](development.md) - General development practices
- [Environment Setup](environment-setup.md) - System requirements and setup
- [Docker Images](docker-images.md) - Container image details 