#!/bin/bash
set -e

echo "🔍 Checking environment configuration..."

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    touch .env
fi

# Function to append variable to .env if not present
append_if_missing() {
    local var_name="$1"
    local var_value="$2"
    local comment="$3"
    
    if ! grep -q "^$var_name=" .env; then
        if [ -n "$comment" ]; then
            echo "" >> .env
            echo "# $comment" >> .env
        fi
        echo "$var_name=$var_value" >> .env
        echo "✅ Added $var_name=$var_value"
    else
        echo "ℹ️  $var_name already configured"
    fi
    return 0
}

# Function to get current platform
get_current_platform() {
    grep "^MODEL_PLATFORM=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo ""
}

# Function to determine default platform based on available API keys
determine_default_platform() {
    if grep -q "^OPENAI_API_KEY=" .env && ! grep -q "^OPENAI_API_KEY=your_openai_api_key_here" .env; then
        echo "openai"
    elif grep -q "^AWS_ACCESS_KEY_ID=" .env; then
        echo "aws_bedrock"
    elif grep -q "^ANTHROPIC_API_KEY=" .env; then
        echo "anthropic"
    else
        echo "ollama"
    fi
}

# Function to get default model ID for platform
get_default_model_id() {
    local platform="$1"
    case "$platform" in
        "openai")
            echo "gpt-4o-mini"
            ;;
        "aws_bedrock")
            echo "anthropic.claude-3-5-sonnet-20241022-v1:0"
            ;;
        "anthropic")
            echo "claude-3-5-sonnet-20241022"
            ;;
        "ollama")
            echo "llama3.1:8b"
            ;;
        *)
            echo "llama3.1:8b"
            ;;
    esac
}

# Check current platform
CURRENT_PLATFORM=$(get_current_platform)

# If no platform is set, determine default based on available API keys
if [ -z "$CURRENT_PLATFORM" ]; then
    DEFAULT_PLATFORM=$(determine_default_platform)
    DEFAULT_MODEL_ID=$(get_default_model_id "$DEFAULT_PLATFORM")
    
    echo "🤖 No MODEL_PLATFORM configured. Detecting available API keys..."
    
    if [ "$DEFAULT_PLATFORM" = "ollama" ]; then
        echo "📋 No API keys found. Defaulting to Ollama (local model)"
        append_if_missing "MODEL_PLATFORM" "ollama" "Model platform (openai|aws_bedrock|anthropic|ollama)"
        append_if_missing "MODEL_ID" "$DEFAULT_MODEL_ID" "Model identifier"
    else
        echo "🔑 Found API key for $DEFAULT_PLATFORM. Setting as default."
        append_if_missing "MODEL_PLATFORM" "$DEFAULT_PLATFORM" "Model platform (openai|aws_bedrock|anthropic|ollama)"
        append_if_missing "MODEL_ID" "$DEFAULT_MODEL_ID" "Model identifier"
    fi
else
    echo "ℹ️  MODEL_PLATFORM already set to: $CURRENT_PLATFORM"
    
    # Check if MODEL_ID is set for current platform
    if ! grep -q "^MODEL_ID=" .env; then
        DEFAULT_MODEL_ID=$(get_default_model_id "$CURRENT_PLATFORM")
        append_if_missing "MODEL_ID" "$DEFAULT_MODEL_ID" "Model identifier"
    fi
fi

# Append other required demo settings
echo ""
echo "📋 Checking required demo settings..."

append_if_missing "API_CALLS_ENABLED" "true" "Enable API calls for demo"
append_if_missing "API_CALLS_ALLOWED_URLS" "http://ecommerce-mock:8000,http://localhost:8000,http://localhost:8001" "Allowed URLs for API calls"
append_if_missing "CORS_ALLOW_ORIGINS" "http://localhost:3001,http://127.0.0.1:3001" "CORS allowed origins"
append_if_missing "AUTH_ENABLED" "false" "Disable authentication for demo"

# Check API keys for current platform
CURRENT_PLATFORM=$(get_current_platform)
echo ""
echo "🔑 Checking API keys for platform: $CURRENT_PLATFORM"

MISSING_KEYS=""
case "$CURRENT_PLATFORM" in
    "openai")
        if ! grep -q "^OPENAI_API_KEY=" .env || grep -q "^OPENAI_API_KEY=your_openai_api_key_here" .env; then
            MISSING_KEYS="OpenAI"
        fi
        ;;
    "aws_bedrock")
        if ! grep -q "^AWS_ACCESS_KEY_ID=" .env; then
            MISSING_KEYS="AWS"
        fi
        ;;
    "anthropic")
        if ! grep -q "^ANTHROPIC_API_KEY=" .env; then
            MISSING_KEYS="Anthropic"
        fi
        ;;
    "ollama")
        # Ollama doesn't require API keys
        echo "✅ Ollama platform - no API key required"
        ;;
esac

if [ -n "$MISSING_KEYS" ]; then
    echo "⚠️  API key missing for platform $CURRENT_PLATFORM: $MISSING_KEYS"
    echo "   Please configure the appropriate API key:"
    case "$CURRENT_PLATFORM" in
        "openai")
            echo "   - OpenAI: https://platform.openai.com/api-keys"
            echo "   - Add to .env: OPENAI_API_KEY=your_actual_key"
            ;;
        "aws_bedrock")
            echo "   - AWS Bedrock: Configure AWS credentials"
            echo "   - Add to .env: AWS_ACCESS_KEY_ID=your_key"
            echo "   - Add to .env: AWS_SECRET_ACCESS_KEY=your_secret"
            echo "   - Add to .env: AWS_DEFAULT_REGION=your_region"
            ;;
        "anthropic")
            echo "   - Anthropic: https://console.anthropic.com/"
            echo "   - Add to .env: ANTHROPIC_API_KEY=your_actual_key"
            ;;
    esac
    echo ""
    read -p "Press Enter after setting your API key, or Ctrl+C to cancel..."
else
    echo "✅ Environment configuration complete"
fi

echo ""
echo "🎯 Ready to run UI demo!"

# Check and install dependencies if needed
echo ""
echo "📦 Checking dependencies..."
if [ ! -d ".venv" ] && [ ! -d "venv" ]; then
    echo "📦 Installing dependencies..."
    make install
else
    echo "✅ Dependencies already installed"
fi

# Create necessary directories
echo ""
echo "📁 Creating necessary directories..."
mkdir -p logs data/api_specs models
echo "✅ Directories created"

# Create demo API spec if it doesn't exist
echo ""
echo "📋 Checking API specs..."
if [ ! -f "data/api_specs/ecommerce_api.yaml" ]; then
    echo "📋 Creating demo API spec..."
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
                  type: object
                  properties:
                    id: { type: integer }
                    name: { type: string }
                    price: { type: number }
EOF
    echo "✅ Demo API spec created"
else
    echo "✅ API spec already exists"
fi

# Check Docker requirements
echo ""
echo "🐳 Checking Docker requirements..."
if ! command -v docker >/dev/null 2>&1; then
    echo "❌ Docker is required but not installed"
    echo "   Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running"
    echo "   Please start Docker and try again"
    exit 1
fi

if ! command -v docker-compose >/dev/null 2>&1; then
    echo "❌ Docker Compose is required but not installed"
    echo "   Please install Docker Compose from https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker requirements met"
echo ""
echo "✅ All prerequisites ready!" 