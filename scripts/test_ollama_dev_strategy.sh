#!/bin/bash

# Test script for Ollama Development Strategy
# This script tests the efficient model path strategy

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Testing Ollama Development Strategy ===${NC}"
echo ""

# Test 1: Check if the setup script exists
echo -e "${YELLOW}Test 1: Checking setup script...${NC}"
if [[ -f "scripts/setup_ollama_dev.sh" ]]; then
    echo -e "${GREEN}✓ Setup script exists${NC}"
else
    echo -e "${RED}✗ Setup script not found${NC}"
    exit 1
fi

# Test 2: Check if the script is executable
echo -e "${YELLOW}Test 2: Checking script permissions...${NC}"
if [[ -x "scripts/setup_ollama_dev.sh" ]]; then
    echo -e "${GREEN}✓ Setup script is executable${NC}"
else
    echo -e "${RED}✗ Setup script is not executable${NC}"
    exit 1
fi

# Test 3: Test model path detection (without starting services)
echo -e "${YELLOW}Test 3: Testing model path detection...${NC}"

# Source the functions from the setup script
source scripts/setup_ollama_dev.sh

# Test the find_ollama_models_path function
models_path=$(find_ollama_models_path 2>/dev/null)

if [[ -n "$models_path" ]]; then
    echo -e "${GREEN}✓ Found existing models at: $models_path${NC}"
else
    echo -e "${YELLOW}⚠ No existing models found (will use containerized)${NC}"
fi

# Test 4: Test Docker Compose configuration generation
echo -e "${YELLOW}Test 4: Testing configuration generation...${NC}"

# Create a temporary test configuration
create_dev_compose_config "$models_path" 2>/dev/null

if [[ -f "docker-compose.dev.yml" ]]; then
    echo -e "${GREEN}✓ Configuration file generated${NC}"
    
    # Test if the configuration is valid
    if docker compose -f docker-compose.dev.yml config > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Configuration is valid${NC}"
    else
        echo -e "${RED}✗ Configuration is invalid${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Configuration file not generated${NC}"
    exit 1
fi

# Test 5: Check if the configuration uses the correct model path
echo -e "${YELLOW}Test 5: Checking model path in configuration...${NC}"

if [[ -n "$models_path" ]]; then
    if grep -q "$models_path" docker-compose.dev.yml; then
        echo -e "${GREEN}✓ Configuration correctly mounts existing models${NC}"
    else
        echo -e "${RED}✗ Configuration does not mount existing models${NC}"
        exit 1
    fi
else
    if grep -q "ollama_data:/root/.ollama" docker-compose.dev.yml; then
        echo -e "${GREEN}✓ Configuration correctly uses containerized models${NC}"
    else
        echo -e "${RED}✗ Configuration does not use containerized models${NC}"
        exit 1
    fi
fi

# Test 6: Check Makefile targets
echo -e "${YELLOW}Test 6: Checking Makefile targets...${NC}"

if grep -q "serve-dev" Makefile; then
    echo -e "${GREEN}✓ serve-dev target exists in Makefile${NC}"
else
    echo -e "${RED}✗ serve-dev target not found in Makefile${NC}"
    exit 1
fi

if grep -q "stop-dev" Makefile; then
    echo -e "${GREEN}✓ stop-dev target exists in Makefile${NC}"
else
    echo -e "${RED}✗ stop-dev target not found in Makefile${NC}"
    exit 1
fi

# Test 7: Check documentation
echo -e "${YELLOW}Test 7: Checking documentation...${NC}"

if [[ -f "docs/ollama-dev-strategy.md" ]]; then
    echo -e "${GREEN}✓ Documentation exists${NC}"
else
    echo -e "${RED}✗ Documentation not found${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=== All Tests Passed! ===${NC}"
echo ""
echo -e "${BLUE}Strategy Summary:${NC}"
if [[ -n "$models_path" ]]; then
    echo -e "  ✓ Using existing models from: $models_path"
    echo -e "  ✓ No need to download models"
else
    echo -e "  ✓ Using containerized models"
    echo -e "  ✓ Models will be downloaded as needed"
fi
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  Run 'make serve-dev' to start the development environment"
echo -e "  Run 'make stop-dev' to stop the development services"
echo "" 