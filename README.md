# API Assistant

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/your-org/api-assistant/actions)

Query Talk your APIs.

**API Assistant** is an open-source conversational AI agent for rapid API integration, testing, and exploration. Instantly chat with your APIs, validate endpoints, and automate integration flows—all powered by modern LLMs.

---

## 🚀 Quick Start

### 🎯 Fast-Track UI Demo (Recommended)
```bash
# 1. Clone the repository
git clone <repository-url>
cd api-assistant

# 2. Run the one-liner (handles everything on-demand)
./quick-start.sh

# 3. Open your browser to http://localhost:3001
```

**Alternative**: Use `make ui-run` directly for the same on-demand setup

**Requirements**: Python 3.8+, Docker, OpenAI API key

### Option 1: Local Development
```bash
# 1. Install Poetry if needed
pip install poetry

# 2. Clone & install dependencies
git clone <repository-url>
cd api-assistant
poetry install

# 3. Configure environment
cp .env.example .env  # Edit as needed

# 4. Run the agent (example)
poetry run python -m api_assistant.server
```

### Option 2: Docker with Ollama
```bash
# 1. Clone the repository
git clone <repository-url>
cd api-assistant

# 2. Set up Ollama with llama3.1:8b
./scripts/setup_ollama_advanced.sh

# 3. Start the API Assistant with Docker
docker compose up -d

# 4. Access the service
curl http://localhost:8080/health
```

For detailed Ollama setup instructions, see [docs/ollama-setup.md](docs/ollama-setup.md).

---

## ✨ Features
- **Conversational API Testing**: Chat with your API, get instant feedback
- **OpenAPI/Swagger Support**: Import specs for deep understanding
- **Multi-Model**: Anthropic Claude, Llama, Phi-4, and more
- **Built-in HTTP Tools**: Make real API calls from chat
- **Automated Evaluation**: Integrated test and eval suite
- **Interactive UI Demo**: Beautiful web interface with streaming responses
- **Real-time Tool Execution**: Watch API calls happen live in the UI
- **Markdown Rendering**: Rich formatting for responses and documentation

---

## 🛠 Example Usage

```python
from api_assistant.agent.api_assistant_agent import APIAssistant
agent = APIAssistant()
response = agent.chat("Test the /users endpoint")
print(response)
```

---

## 🧩 Project Structure

- `src/api_assistant/` – Core agent, models, tools, config
- `tests/` – Unit & evaluation tests
- `docs/` – Documentation & guides

---

## 🤝 Contributing
We welcome issues and PRs! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License
MIT. See [LICENSE](LICENSE). # Test commit signing
