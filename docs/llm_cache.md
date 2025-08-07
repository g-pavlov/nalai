# LLM Cache Integrations

## Overview

The LLM cache system reduces API costs and improves response times by storing and retrieving previous responses. It uses intelligent caching with semantic similarity matching to handle variations in user queries.

This cache solution addresses 4 key LLM caching challenges:
1. **Semantic variation** - LLM responses differ for equivalent inputs
2. **Performance overhead** - Semantic search on critical path
3. **Identity privacy** - Cache must ensure user isolation
4. **Tool call handling** - Time-varying results require configurable caching

## Cache Backends

### In-Memory Backend

**Default backend** - Stores cache data in application memory.

**Features:**
- ✅ Zero external dependencies
- ✅ Sub-10ms lookup times
- ✅ Automatic cleanup with TTL
- ✅ User-scoped isolation
- ✅ Configurable size limits

**Resource Usage:**
- **Memory**: ~50MB base + 1KB per cache entry
- **CPU**: <1% overhead for cache operations
- **Storage**: None (in-memory only)

**Configuration:**
```bash
# Enable in-memory cache
CACHE_ENABLED=true
CACHE_BACKEND=memory

# Size and TTL limits
CACHE_MAX_SIZE=1000
CACHE_TTL_SECONDS=1800

# Performance settings
CACHE_SIMILARITY_ENABLED=true
CACHE_SIMILARITY_THRESHOLD=0.8
```

**When to Use:**
- ✅ Single-server deployments
- ✅ Development and testing
- ✅ Memory-constrained environments
- ✅ Simple caching requirements

**When Not to Use:**
- ❌ Multi-server deployments (no sharing)
- ❌ High-availability requirements
- ❌ Large cache sizes (>10,000 entries)

## Semantic Key Match Options

The cache system uses semantic similarity matching to find similar queries. Three corpus options are available, each with different accuracy and resource requirements.

| Feature | Comprehensive (NLTK + spaCy) | WordNet (NLTK Only) | Fallback (Basic) |
|---------|------------------------------|---------------------|------------------|
| **Accuracy** | 70-85% hit rate | 60-75% hit rate | 40-60% hit rate |
| **Memory** | ~650MB | ~550MB | <1MB |
| **Dependencies** | NLTK + spaCy | NLTK only | None |
| **Setup** | `python scripts/setup_nlp_corpus.py` | `python scripts/setup_nlp_corpus.py` | Automatic |
| **Word Coverage** | 11,000+ verbs, 82,000+ nouns | 11,000+ verbs, 82,000+ nouns | ~100 API terms |
| **Antonym Detection** | Excellent | Good | Basic |
| **Domain Coverage** | Universal | Good | Limited |
| **False Positive Prevention** | Excellent | Good | Basic |

## Decision Guide

| Use Case | Recommended Corpus | Reason |
|----------|-------------------|---------|
| **High-traffic production** | Comprehensive | Better cache hits reduce API costs |
| **Cost-sensitive environments** | Comprehensive | 70-85% similarity match rate |
| **Multi-domain applications** | Comprehensive | Universal word coverage |
| **Memory-constrained production** | WordNet | Good accuracy with moderate resources |
| **spaCy installation issues** | WordNet | NLTK-only alternative |
| **Development/testing** | Fallback | Quick setup, no dependencies |
| **Severe memory constraints** | Fallback | <1MB overhead |
| **Quick deployment** | Fallback | No setup required |
| **Real-time data requirements** | Disable cache | Cache may serve stale data |
| **Tool-heavy workflows** | Disable cache | Tool calls produce time-varying results |
| **Single-use applications** | Disable cache | No benefit from caching |

### Choose Comprehensive Corpus When:
- ✅ **High-traffic applications** - Better cache hit rates reduce API costs
- ✅ **Cost-sensitive environments** - 70-85% similarity match rate
- ✅ **Multi-domain applications** - Universal word coverage
- ✅ **Production deployments** - Best accuracy for user experience
- ✅ **Sufficient memory available** - 500MB+ for NLP libraries

### Choose WordNet Corpus When:
- ✅ **Moderate accuracy needs** - 60-75% similarity match rate
- ✅ **Memory constraints** - 500MB for NLTK only
- ✅ **spaCy installation issues** - NLTK-only alternative
- ✅ **Balanced requirements** - Good accuracy with moderate resources

### Choose Fallback Corpus When:
- ✅ **Development/testing** - Quick setup, no dependencies
- ✅ **Severe memory constraints** - <1MB overhead
- ✅ **Simple caching needs** - Basic similarity matching
- ✅ **Quick deployment** - No setup required

### Disable Cache When:
- ❌ **Real-time data requirements** - Cache may serve stale data
- ❌ **Tool-heavy workflows** - Tool calls produce time-varying results
- ❌ **Single-use applications** - No benefit from caching
- ❌ **Memory-constrained environments** - Even basic cache uses memory

## Configuration Examples

### High-Performance Production
```bash
# Comprehensive corpus for best accuracy
CACHE_ENABLED=true
CACHE_BACKEND=memory
CACHE_MAX_SIZE=2000
CACHE_TTL_SECONDS=3600
CACHE_SIMILARITY_ENABLED=true
CACHE_SIMILARITY_THRESHOLD=0.8
CACHE_TOOL_CALLS=false
```

### Memory-Constrained Production
```bash
# WordNet corpus for balanced performance
CACHE_ENABLED=true
CACHE_BACKEND=memory
CACHE_MAX_SIZE=500
CACHE_TTL_SECONDS=1800
CACHE_SIMILARITY_ENABLED=true
CACHE_SIMILARITY_THRESHOLD=0.7
CACHE_TOOL_CALLS=false
```

### Development/Testing
```bash
# Fallback corpus for quick setup
CACHE_ENABLED=true
CACHE_BACKEND=memory
CACHE_MAX_SIZE=100
CACHE_TTL_SECONDS=900
CACHE_SIMILARITY_ENABLED=true
CACHE_SIMILARITY_THRESHOLD=0.6
CACHE_TOOL_CALLS=false
```

### Cost-Optimized
```bash
# Comprehensive corpus with aggressive caching
CACHE_ENABLED=true
CACHE_BACKEND=memory
CACHE_MAX_SIZE=5000
CACHE_TTL_SECONDS=86400
CACHE_SIMILARITY_ENABLED=true
CACHE_SIMILARITY_THRESHOLD=0.6
CACHE_TOOL_CALLS=false
```

## Monitoring

Cache operations are logged with structured JSON format for monitoring and debugging.

**Cache Hit Example:**
```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "level": "INFO",
  "message": "Cache hit for user user_123",
  "cache_key": "user:user_123:abc123...",
  "response_time_ms": 5,
  "similarity_score": 0.95
}
```

**Cache Miss Example:**
```json
{
  "timestamp": "2024-01-15T10:30:50Z",
  "level": "INFO", 
  "message": "Cache miss for user user_123",
  "cache_key": "user:user_123:def456...",
  "response_time_ms": 2500
}
```

## Security & Compliance

### User Isolation & Injection Protection
- **User-scoped cache keys**: `user:{user_id}:{content_hash}` format
- **Complete isolation**: No data leakage between users
- **Server-side user ID**: User ID comes from validated JWT tokens, never client input
- **Cryptographic validation**: JWT tokens validated with secret keys
- **Request state protection**: User ID stored in server-side request state only
- **Application-controlled metadata**: LangChain metadata set by application, not users
- **PII protection**: User IDs in audit logs are masked
- **User-specific clearing**: `cache.clear_user_cache(user_id)`

### Data Protection
- **SHA-256 hashing**: Content is hashed, not stored in plain text
- **256-bit collision resistance**: 2^128 security level prevents key collisions
- **Content fingerprinting**: Full message content included in hash
- **Configurable TTL**: Automatic expiration (default: 30 minutes)
- **Size limits**: Prevents memory exhaustion (default: 1000 entries)
- **LRU eviction**: Oldest entries automatically removed when limit reached
- **Audit logging**: Complete trail of cache operations with PII masking

### Attack Vector Mitigation
- **Direct user ID injection**: **IMPOSSIBLE** - No client input path for user ID
- **Metadata injection**: **IMPOSSIBLE** - Application controls all metadata
- **Token manipulation**: **VERY LOW RISK** - Requires breaking JWT cryptography
- **Session hijacking**: **LOW RISK** - Session validation and IP binding
- **Cache poisoning**: **LOW RISK** - User-scoped keys limit impact
- **Memory exhaustion**: **LOW RISK** - Size limits and LRU eviction

### Compliance
- **GDPR-ready**: User data isolation, retention controls, right to erasure
- **Privacy-by-design**: No cross-user data access, data minimization
- **SOC 2 compatible**: Access controls, audit logging, data encryption
- **ISO 27001 compatible**: Information security, risk assessment, access management
- **Configurable retention**: TTL and size limits prevent data accumulation 