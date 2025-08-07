#!/bin/bash

# Fast-track setup for API Assistant UI Demo
# This script sets up everything needed to run the UI demo after a fresh git clone

set -e  # Exit on any error

echo "🚀 Fast-track setup for API Assistant UI Demo"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -f "docker-compose.yml" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

print_status "Checking system requirements..."

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "Python 3.8+ is required, found $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION found"

# Check Docker
if ! command -v docker >/dev/null 2>&1; then
    print_error "Docker is required but not installed"
    print_warning "Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running"
    print_warning "Please start Docker and try again"
    exit 1
fi

print_success "Docker is available and running"

# Check Docker Compose
if ! command -v docker-compose >/dev/null 2>&1; then
    print_error "Docker Compose is required but not installed"
    print_warning "Please install Docker Compose from https://docs.docker.com/compose/install/"
    exit 1
fi

print_success "Docker Compose is available"

# Install Poetry if not present
if ! command -v poetry >/dev/null 2>&1; then
    print_status "Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
    print_success "Poetry installed"
else
    print_success "Poetry already installed: $(poetry --version)"
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
poetry install --with=testing
print_success "Python dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_status "Creating .env file with default configuration..."
    cat > .env << 'EOF'
# API Assistant Configuration
# ==========================

# Model Configuration
NALAI_MODEL_ID=gpt-4o-mini
NALAI_MODEL_PLATFORM=openai
NALAI_MODEL_TEMPERATURE=0.0
NALAI_MODEL_MAX_TOKENS=4000

# OpenAI Configuration (REQUIRED for demo)
# Get your API key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# AWS Configuration (optional - for Bedrock models)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1

# Ollama Configuration
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_PORT=11435

# API Behavior
API_CALLS_ENABLED=true
API_CALLS_ALLOWED_URLS=http://ecommerce-mock:8000,http://localhost:8000,http://localhost:8001

# Cache Settings
CACHE_ENABLED=true
CACHE_MAX_SIZE=1000
CACHE_TTL_HOURS=1

# Development Settings
AUTH_ENABLED=false
LOGGING_LEVEL=INFO

# CORS Configuration
CORS_ALLOW_ORIGINS=http://localhost:3001,http://127.0.0.1:3001

# Authentication (disabled for demo)
AUTH_ENABLED=false
EOF
    print_success ".env file created"
    print_warning "⚠️  IMPORTANT: Please edit .env and set your OPENAI_API_KEY"
    print_warning "   Get your API key from: https://platform.openai.com/api-keys"
else
    print_success ".env file already exists"
fi

# Check if OPENAI_API_KEY is set
if [ -f ".env" ]; then
    if grep -q "OPENAI_API_KEY=your_openai_api_key_here" .env || ! grep -q "OPENAI_API_KEY=" .env; then
        print_warning "⚠️  OPENAI_API_KEY not configured in .env file"
        print_warning "   Please edit .env and set your OpenAI API key"
        print_warning "   Get your API key from: https://platform.openai.com/api-keys"
        echo ""
        print_status "You can continue with the setup, but the demo won't work without a valid API key"
        read -p "Press Enter to continue anyway, or Ctrl+C to stop and configure the API key..."
    else
        print_success "OPENAI_API_KEY is configured"
    fi
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs data/api_specs models
print_success "Directories created"

# Check if API specs exist
if [ ! -f "data/api_specs/ecommerce_api.yaml" ]; then
    print_status "API specs not found, creating demo API spec..."
    cat > data/api_specs/ecommerce_api.yaml << 'EOF'
openapi: 3.0.0
info:
  title: E-commerce API
  version: 1.0.0
  description: A mock e-commerce API for demonstration purposes
paths:
  /products:
    get:
      summary: Get all products
      responses:
        '200':
          description: List of products
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Product'
  /products/{id}:
    get:
      summary: Get product by ID
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: integer
      responses:
        '200':
          description: Product details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Product'
components:
  schemas:
    Product:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
        price:
          type: number
        description:
          type: string
EOF
    print_success "Demo API spec created"
fi

# Build Docker images
print_status "Building Docker images (this may take a few minutes)..."
docker-compose build
print_success "Docker images built"

print_success "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Edit .env file and set your OPENAI_API_KEY"
echo "   2. Run: make ui-run"
echo ""
echo "🌐 Once running, you can access:"
echo "   • UI Demo: http://localhost:3001"
echo "   • API Docs: http://localhost:8000/docs"
echo "   • Mock API: http://localhost:8001"
echo ""
print_warning "Note: The first run may take a few minutes to download models and start all services" 