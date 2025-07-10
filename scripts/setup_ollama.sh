#!/bin/bash

# Ollama Setup Script
# This script sets up Ollama with parameterized configuration

set -e

# Default configuration
OLLAMA_PORT=${OLLAMA_PORT:-11434}
OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.1:8b}
OLLAMA_TARGET_OS=${OLLAMA_TARGET_OS:-linux}
OLLAMA_TARGET_ARCH=${OLLAMA_TARGET_ARCH:-amd64}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Ollama with the following configuration:${NC}"
echo "  Port: $OLLAMA_PORT"
echo "  Model: $OLLAMA_MODEL"
echo "  Target OS: $OLLAMA_TARGET_OS"
echo "  Target Architecture: $OLLAMA_TARGET_ARCH"
echo ""

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
        exit 1
    fi
}

# Function to check if Docker Compose is available
check_docker_compose() {
    if ! command -v docker-compose > /dev/null 2>&1 && ! docker compose version > /dev/null 2>&1; then
        echo -e "${RED}Error: Docker Compose is not available. Please install Docker Compose and try again.${NC}"
        exit 1
    fi
}

# Function to start Ollama service
start_ollama() {
    echo -e "${YELLOW}Starting Ollama service...${NC}"
    
    # Use docker compose if available, otherwise docker-compose
    if docker compose version > /dev/null 2>&1; then
        docker compose up -d ollama
    else
        docker-compose up -d ollama
    fi
    
    echo -e "${GREEN}Ollama service started successfully!${NC}"
}

# Function to wait for Ollama to be ready
wait_for_ollama() {
    echo -e "${YELLOW}Waiting for Ollama to be ready...${NC}"
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:$OLLAMA_PORT/api/tags" > /dev/null 2>&1; then
            echo -e "${GREEN}Ollama is ready!${NC}"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}Error: Ollama failed to start within the expected time.${NC}"
    return 1
}

# Function to pull the specified model
pull_model() {
    echo -e "${YELLOW}Pulling model: $OLLAMA_MODEL${NC}"
    echo "This may take several minutes depending on your internet connection and model size..."
    
    if ! curl -X POST "http://localhost:$OLLAMA_PORT/api/pull" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$OLLAMA_MODEL\"}" > /dev/null 2>&1; then
        echo -e "${RED}Error: Failed to pull model $OLLAMA_MODEL${NC}"
        return 1
    fi
    
    echo -e "${GREEN}Model $OLLAMA_MODEL pulled successfully!${NC}"
}

# Function to list available models
list_models() {
    echo -e "${YELLOW}Available models:${NC}"
    curl -s "http://localhost:$OLLAMA_PORT/api/tags" | jq -r '.models[] | "  - \(.name) (\(.size | . / 1024 / 1024 / 1024 | round)GB)"' 2>/dev/null || echo "  No models found or jq not available"
}

# Main execution
main() {
    echo -e "${GREEN}=== Ollama Setup Script ===${NC}"
    echo ""
    
    check_docker
    check_docker_compose
    
    start_ollama
    wait_for_ollama
    
    if [ $? -eq 0 ]; then
        pull_model
        echo ""
        list_models
        echo ""
        echo -e "${GREEN}Setup complete! Ollama is running on port $OLLAMA_PORT${NC}"
        echo -e "${YELLOW}You can now use the model: $OLLAMA_MODEL${NC}"
    else
        echo -e "${RED}Setup failed. Please check the logs with: docker compose logs ollama${NC}"
        exit 1
    fi
}

# Run main function
main "$@" 