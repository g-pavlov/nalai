# Architecture Decisions

## Overview

Key design decisions that shape the API Assistant architecture, focusing on practical benefits and implementation guidance.

## Runtime Data Management

### **The Challenge**
API specifications and guidelines change frequently, but rebuilding containers for every data update is inefficient and disruptive.

### **The Solution**
**Configurable External Data Loading**: Single source with configurable path

| **Scenario** | **Path Used** | **Resolution** |
|--------------|---------------|----------------|
| **No API_SPECS_PATH set** | `data/api_specs` (default) | ✅ Works if `./data/api_specs/` exists, ❌ Fails with FileNotFoundError if missing |
| **API_SPECS_PATH configured** | Custom path from env var | ✅ Works if path exists, ❌ Fails with FileNotFoundError if missing |
| **File missing at path** | Any configured path | ❌ Fails with clear error message, no fallback |

### **Why This Rocks**
- **🚀 Zero rebuilds**: Update API specs without touching containers
- **🛠️ Local override**: Use `./data/` directory for custom specs
- **🌍 Environment flexibility**: Different specs per dev/staging/prod
- **📦 Smaller images**: Runtime data not baked into container
- **🔧 Easy testing**: Swap API specs without code changes

### **How to Use It**

#### **Development Setup**
```bash
# Use local data directory (auto-detected)
./data/api_specs/api_summaries.yaml

# Or set custom path
API_SPECS_PATH=./custom_specs python -m api_assistant.server
```

#### **Production Deployment**
```bash
# Docker with volume mount
docker run -v /host/api-specs:/var/lib/nalai/api_specs nalai

# Kubernetes: Mount ConfigMaps as data volumes
# Use ConfigMaps to store API specifications and mount them to /var/lib/nalai/api_specs
```

#### **Configuration**
| Environment | Data Location | Purpose |
|-------------|---------------|---------|
| **Development** | `./data/api_specs/` | Local customization |
| **Production** | `/var/lib/nalai/api_specs` | External management |
| **Container** | Mounted volume | Orchestration ready |

### **Best Practices & Troubleshooting**
- ✅ **Version your data**: Use semantic versioning for API specs
- ✅ **Validate before deploy**: Ensure YAML/JSON is correct
- ✅ **Test updates**: Validate new specs before production

```bash
# Quick health check
curl http://localhost:8080/healthz

# Verify data loading
docker exec container ls -la /var/lib/nalai/api_specs

# Test data format
python -c "import yaml; yaml.safe_load(open('data/api_specs/api_summaries.yaml'))"
```

### **What We Avoided**
- ❌ **Package-embedded**: Would require rebuilds for every data change
- ❌ **Database storage**: Overkill for simple configuration data
- ❌ **Complex fallback logic**: Simplicity over complexity

### **The Result**
**Simple, flexible, and reliable** data management that scales from development to production with minimal complexity.

**Implementation**: `src/api_assistant/services/api_docs_service.py` and `src/api_assistant/config.py`

## LangGraph Workflow Architecture

### **The Challenge**
Building complex AI workflows with state management, human-in-the-loop review, and conditional logic requires a robust orchestration framework.

### **The Solution**
**LangGraph StateGraph with Conditional Workflow**: Multi-node workflow with intelligent routing

| **Node** | **Purpose** | **Next Steps** |
|----------|-------------|----------------|
| **Check Cache** | Entry point, similarity search | Load APIs or End |
| **Load API Summaries** | Load high-level API descriptions | Select Relevant APIs |
| **Select Relevant APIs** | AI-powered API selection | Load Specs or Call Model |
| **Load API Specs** | Load detailed OpenAPI specifications | Call Model |
| **Call Model** | Generate AI response with tools | Human Review, End, or Call API |
| **Call API** | Execute HTTP requests | Call Model |
| **Human Review** | Interrupt for tool validation | Resume workflow |

### **Why This Rocks**
- **🔄 Stateful conversations**: Persistent thread state across interactions
- **🤖 AI-driven routing**: Intelligent workflow decisions based on context
- **👥 Human oversight**: Built-in review for sensitive operations
- **⚡ Caching integration**: Automatic response caching with similarity search
- **🛠️ Tool integration**: Seamless HTTP tool execution
- **📊 Observability**: Clear workflow visualization and debugging

### **How to Use It**

#### **Workflow Creation**
```python
# Create and compile workflow with checkpointing
memory_store = MemorySaver()
agent = APIAssistant()
workflow = create_and_compile_workflow(agent, memory_store)

# Visualize workflow structure
print(workflow.get_graph().draw_ascii())
```

#### **State Management**
```python
# User-scoped thread IDs for isolation
thread_id = f"user:{user_id}:{conversation_id}"

# Persistent state across interactions
config = {"configurable": {"thread_id": thread_id}}
response = await workflow.ainvoke({"messages": [("user", "Hello")]}, config)
```

#### **Human Review Integration**
```python
# Automatic interruption for tool calls
async for event in workflow.astream(input_data, config):
    if event.get("__interrupt__"):
        # Handle human review
        await handle_human_review(event)
```

### **Best Practices & Troubleshooting**
- ✅ **Thread isolation**: Use user-scoped thread IDs for multi-user support
- ✅ **State persistence**: Configure appropriate checkpointing backends
- ✅ **Error handling**: Implement graceful failure recovery
- ✅ **Monitoring**: Track workflow execution metrics

```python
# Check workflow state
snapshot = workflow.get_state(config)
print(f"Current node: {snapshot.next}")

# Debug workflow execution
async for event in workflow.astream_events(input_data, config):
    print(f"Event: {event}")
```

### **What We Avoided**
- ❌ **Linear workflows**: Would limit AI decision-making capabilities
- ❌ **Stateless design**: Would lose conversation context
- ❌ **Manual orchestration**: Would be error-prone and hard to maintain

### **The Result**
**Intelligent, stateful, and human-in-the-loop** workflow orchestration that scales from simple conversations to complex multi-step API integrations.

**Implementation**: `src/api_assistant/core/workflow.py` and `src/api_assistant/core/agent.py`

## Service Layer Architecture

### **The Challenge**
Managing complex business logic across authentication, caching, audit logging, and model services requires clean separation of concerns and flexible backend integration.

### **The Solution**
**Abstract Service Layer with Backend Abstraction**: Provider-agnostic services with lightweight defaults

| **Service** | **Purpose** | **Backends** | **Default** |
|-------------|-------------|--------------|-------------|
| **Auth Service** | Authentication & identity | Standard OIDC, Auth0, Keycloak | In-memory dev mode |
| **Cache Service** | Response caching | Memory, Redis | In-memory LRU |
| **Audit Service** | Security event logging | Memory, External | In-memory with rotation |
| **Checkpointing** | Workflow state persistence | Memory, File, Postgres, Redis | Memory |
| **Thread Access Control** | Thread ownership validation | Memory, Redis | In-memory validation |
| **Model Service** | AI model management | AWS Bedrock, Ollama | Configurable |

### **Why This Rocks**
- **🔧 Zero external dependencies**: All services work out-of-the-box
- **🔄 Backend flexibility**: Easy migration to production backends
- **🛡️ Security by default**: Comprehensive audit and access control
- **⚡ Performance optimized**: Intelligent caching and rate limiting
- **🔍 Observability**: Built-in logging and metrics
- **🧪 Testable**: Clean interfaces with dependency injection

### **How to Use It**

#### **Service Initialization**
```python
# Automatic service creation with defaults
auth_service = get_auth_service()  # In-memory by default
cache_service = get_cache_service()  # LRU cache by default
audit_service = get_audit_service()  # In-memory with rotation

# Configure for production
auth_service = AuthServiceFactory.create_auth_service("standard", config)
cache_service = CacheService(backend="redis", config=redis_config)
```

#### **Middleware Integration**
```python
# Automatic middleware chain
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    identity = await auth_service.authenticate_request(request)
    request.state.identity = identity
    return await call_next(request)
```

#### **Runtime Configuration**
```python
# User-scoped service access
async def process_request(user_context: UserContext):
    # Thread access control
    await thread_access_control.validate_thread_access(user_context.user_id, thread_id)
    
    # Identity-aware caching
    cache_key = f"user:{user_context.user_id}:{request_hash}"
    cached_response = cache_service.get(cache_key)
    
    # Audit logging
    await audit_service.log_access(user_context.user_id, "/api/agent", "invoke")
```

### **Best Practices & Troubleshooting**
- ✅ **Service isolation**: Each service has clear boundaries and interfaces
- ✅ **Configuration transparency**: Individual environment variables for each backend
- ✅ **Error resilience**: Services fail gracefully without breaking the application
- ✅ **Performance monitoring**: Track service metrics and performance

```python
# Service health checks
auth_stats = await auth_service.get_stats()
cache_stats = cache_service.get_stats()
audit_stats = await audit_service.get_stats()

# Backend migration
# 1. Configure new backend
# 2. Test with new backend
# 3. Switch environment variable
# 4. Monitor performance
```

### **What We Avoided**
- ❌ **Monolithic services**: Would be hard to test and maintain
- ❌ **External dependencies**: Would complicate development setup
- ❌ **Complex configuration**: Would be error-prone and hard to debug

### **The Result**
**Modular, testable, and production-ready** service architecture that scales from development to enterprise deployments with minimal configuration complexity.

**Implementation**: 
- Auth: `src/api_assistant/services/auth_service.py`
- Cache: `src/api_assistant/services/cache_service.py`
- Audit: `src/api_assistant/services/audit_service.py`
- Checkpointing: `src/api_assistant/services/checkpointing_service.py`
- Thread Access: `src/api_assistant/services/thread_access_control.py`

## Access Control Architecture

### **The Challenge**
Providing secure multi-user isolation while maintaining lightweight development defaults and supporting enterprise authentication systems.

### **The Solution**
**Multi-Layer Security with Lightweight Defaults**: Authentication, authorization, and audit with optional external backends

| **Layer** | **Component** | **Purpose** | **Default** |
|-----------|---------------|-------------|-------------|
| **Authentication** | Auth Service | User identity verification | JWT/OIDC validation |
| **Authorization** | Thread Access Control | Resource ownership validation | In-memory validation |
| **Data Isolation** | User-scoped IDs | Natural data separation | `user:{user_id}:{thread_id}` |
| **Audit Logging** | Audit Service | Security event tracking | In-memory with rotation |
| **Token Management** | API Token Service | Service delegation/CC | Configurable modes |

### **Why This Rocks**
- **🔐 Security by design**: Multiple layers of protection
- **👥 Multi-user ready**: Complete user isolation out-of-the-box
- **🏢 Enterprise compatible**: Works with external auth (Istio/K8s)
- **🚀 Development friendly**: Zero external dependencies required
- **📊 Compliance ready**: Comprehensive audit trail
- **🔄 Flexible deployment**: Supports all deployment scenarios

### **How to Use It**

#### **Development Setup**
```bash
# Zero external dependencies - everything in-memory
AUTH_ENABLED=true
AUTH_PROVIDER=standard
AUTH_MODE=client_credentials
AUTH_VALIDATE_TOKENS=true
AUTH_AUDIT_ENABLED=true
CACHE_BACKEND=memory
CHECKPOINTING_BACKEND=memory
AUDIT_BACKEND=memory
# No external services required - works out-of-the-box
```

#### **Production Deployment**
```bash
# Use external backends for scalability
AUTH_ENABLED=true
AUTH_PROVIDER=standard
AUTH_MODE=client_credentials
CACHE_BACKEND=redis
CACHE_REDIS_URL=redis://redis:6379
CHECKPOINTING_BACKEND=postgres
CHECKPOINTING_POSTGRES_URL=postgresql://user:pass@postgres/db
AUDIT_BACKEND=external
AUDIT_EXTERNAL_URL=http://audit-service:8080
```

#### **Enterprise Integration**
```bash
# Auth handled externally (e.g., Istio/K8s) - disable token validation
AUTH_ENABLED=true
AUTH_PROVIDER=standard
AUTH_MODE=client_credentials
AUTH_VALIDATE_TOKENS=false  # Auth handled externally
AUTH_AUDIT_ENABLED=true
CACHE_BACKEND=redis
CHECKPOINTING_BACKEND=postgres
AUDIT_BACKEND=external
AUDIT_EXTERNAL_URL=http://audit-service:8080
# Agent focuses on business logic, auth handled by infrastructure
```

### **Best Practices & Troubleshooting**
- ✅ **Thread validation**: Always validate thread ownership before operations
- ✅ **User-scoped isolation**: Use `user:{user_id}:{thread_id}` format consistently
- ✅ **Audit everything**: Log all access events for compliance
- ✅ **Token security**: Secure token storage and transmission

```python
# Thread access validation
is_owner = await thread_access_control.validate_thread_access(user_id, thread_id)
if not is_owner:
    raise HTTPException(status_code=403, detail="Access denied")

# User-scoped thread ID creation
user_scoped_id = await thread_access_control.create_user_scoped_thread_id(user_id, thread_id)

# Audit logging
await audit_service.log_thread_access(user_id, thread_id, "create", success=True)
```

### **What We Avoided**
- ❌ **Data isolation only**: Would not provide true access control
- ❌ **Complex RBAC**: Would overcomplicate for most use cases
- ❌ **External auth only**: Would break development workflow

### **The Result**
**Secure, scalable, and developer-friendly** access control that works seamlessly from development to enterprise production environments.

**Implementation**: `src/api_assistant/services/thread_access_control.py` and `src/api_assistant/server/runtime_config.py`

**Related Documentation**: See [Access Control Architecture](access-control-architecture.md) for detailed implementation and [Security Overview](security.md) for compliance details.

## Modular Tool System

### **The Challenge**
Providing safe, extensible HTTP tool capabilities while maintaining security boundaries and supporting human-in-the-loop review.

### **The Solution**
**Extensible HTTP Toolkit with Safety Controls**: Modular tools with built-in security and review workflows

| **Component** | **Purpose** | **Features** |
|---------------|-------------|--------------|
| **HTTP Toolkit** | Core HTTP operations | GET, POST, PUT, DELETE, PATCH |
| **Safety Controls** | Tool validation | URL validation, method restrictions |
| **Rate Limiting** | API protection | Cross-process rate limiting |
| **Human Review** | Tool call validation | Interrupt workflow for approval |
| **Error Handling** | Graceful failures | Comprehensive error responses |
| **Caching** | Response optimization | Identity-aware response caching |

### **Why This Rocks**
- **🛡️ Security first**: Built-in URL validation and method restrictions
- **🔧 Extensible**: Easy to add new tools and capabilities
- **👥 Human oversight**: Automatic review for sensitive operations
- **⚡ Performance**: Intelligent caching and rate limiting
- **🔄 Resilience**: Comprehensive error handling and retry logic
- **📊 Observability**: Detailed logging and metrics

### **How to Use It**

#### **Tool Integration**
```python
# Automatic tool binding to models
if settings.enable_api_calls:
    model = model.bind_tools(http_toolkit.get_tools())

# Safety validation
if http_toolkit.is_safe_tool(tool_name):
    return NODE_CALL_API
else:
    return NODE_HUMAN_REVIEW
```

#### **Human Review Workflow**
```python
# Automatic interruption for tool calls
def determine_workflow_action(state: AgentState):
    if tool_calls and not is_safe_tool(tool_name):
        return NODE_HUMAN_REVIEW  # Interrupt for approval
    elif tool_calls and is_safe_tool(tool_name):
        return NODE_CALL_API      # Execute directly
    else:
        return END                # Complete workflow
```

#### **Rate Limiting Integration**
```python
# Cross-process rate limiting
rate_limiter = create_model_rate_limiter(model_platform, model_id)
if rate_limiter:
    model_kwargs["rate_limiter"] = rate_limiter

# Tool-specific rate limiting
http_toolkit = HttpRequestsToolkit()
tools = http_toolkit.get_tools()  # Includes rate limiting
```

### **Best Practices & Troubleshooting**
- ✅ **Tool validation**: Always validate tool calls before execution
- ✅ **Safety controls**: Use built-in safety mechanisms
- ✅ **Human review**: Enable review for sensitive operations
- ✅ **Error handling**: Implement graceful failure recovery

```python
# Tool safety check
def is_safe_tool(tool_name: str) -> bool:
    safe_tools = {"http_get", "http_post", "http_put", "http_delete"}
    return tool_name in safe_tools

# Human review integration
if not is_safe_tool(tool_call_name):
    return NODE_HUMAN_REVIEW  # Require human approval
```

### **What We Avoided**
- ❌ **Unrestricted tools**: Would pose security risks
- ❌ **No human oversight**: Would allow dangerous operations
- ❌ **Monolithic design**: Would be hard to extend and test

### **The Result**
**Safe, extensible, and human-in-the-loop** tool system that provides powerful API integration capabilities while maintaining security and oversight.

**Implementation**: `src/api_assistant/tools/http_requests.py`

---

*More architecture decisions will be added here as the project evolves.*

**Related Documentation**:
- [Access Control Architecture](access-control-architecture.md) - Detailed access control implementation
- [Security Overview](security.md) - Security architecture and compliance
- [Development Guide](development.md) - Development practices and workflows 